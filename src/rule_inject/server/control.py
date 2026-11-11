"""サーバーの稼働の状態（処理中の呼び出しと要求の数・再起動と更新のマーカー）と、再起動の停止の進め方。"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mcp.server.mcpserver.exceptions import ToolError

if TYPE_CHECKING:
    import uvicorn
    from starlette.types import ASGIApp, Receive, Scope, Send

# 再起動で、処理中の呼び出しの終わりを待つ上限（秒）
STOP_DRAIN_TIMEOUT = 356
# 待ち受けを閉じた後に残った接続を切るまでの上限（秒）。`uvicorn.Config` の `timeout_graceful_shutdown`
GRACEFUL_SHUTDOWN_TIMEOUT = 3
# 停止の待ちで、処理中の呼び出しの数を見直す間隔（秒）
DRAIN_POLL_INTERVAL = 0.1

logger = logging.getLogger(__name__)


class RestartInProgressError(ToolError):
    """再起動を始めた後か、更新が動いている間の呼び出しを断る。"""


class ServerControl:
    """待ち受けのポート・起動した時刻・処理中の呼び出しと要求の数・再起動と更新のマーカーを持ち、再起動の停止を進める。"""

    def __init__(self, *, port: int) -> None:
        """待ち受けているポートを受け、このプロセスのイメージで作った時刻を起動した時刻にする。"""
        self.port = port
        self.pid = os.getpid()
        self.started_at = datetime.now(UTC)
        # 同期のツールは SDK がスレッドで動かすため、数とマーカーの読み込み・書き込みを 1 つずつ行う
        self._lock = threading.Lock()
        self._in_flight = 0
        # 応答を送信し終えていない POST の要求の数（ツールの関数が戻った後も、応答の送信が終わるまで数える）
        self._requests = 0
        self._restarting = False
        self._updating = False
        self._server: uvicorn.Server | None = None
        # 停止を進めるタスク（参照を持って捨てられないようにする）
        self._stop_task: asyncio.Task[None] | None = None

    def attach(self, server: uvicorn.Server) -> None:
        """停止に使用する `uvicorn.Server` を受け取る。"""
        self._server = server

    @property
    def restarting(self) -> bool:
        """再起動を始めたか。"""
        return self._restarting

    @property
    def restart_requested(self) -> bool:
        """`serve` が返った後に再起動するか。Ctrl+C・SIGTERM で終わったときは偽。"""
        return self._restarting

    def guard(self, function: Callable[..., Any]) -> Callable[..., Any]:
        """ツールの関数を包み、再起動の途中なら断り、それ以外は処理中の数を数えて呼ぶ。"""
        # `async def` は `async def` で包み、SDK がイベントループで await できるようにする
        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def guarded_async(*args: Any, **kwargs: Any) -> Any:
                """処理中の数を数えて await する。"""
                self._enter()
                try:
                    return await function(*args, **kwargs)
                finally:
                    self._leave()

            return guarded_async

        @functools.wraps(function)
        def guarded(*args: Any, **kwargs: Any) -> Any:
            """処理中の数を数えて呼ぶ。"""
            self._enter()
            try:
                return function(*args, **kwargs)
            finally:
                self._leave()

        return guarded

    def track(self, app: ASGIApp) -> ASGIApp:
        """ASGI のアプリを包み、POST の要求を受けてから包んだアプリが戻るまでを処理中の要求として数える。"""

        async def tracked(scope: Scope, receive: Receive, send: Send) -> None:
            """POST の要求だけを数えて、包んだアプリへそのまま引き渡す。"""
            # GET（SSE のストリーム）・DELETE・lifespan は終わりを待たないため数えない
            if scope["type"] != "http" or scope["method"] != "POST":
                await app(scope, receive, send)
                return
            with self._lock:
                self._requests += 1
            try:
                # SSE の応答は、応答を送信し終えるか接続が切れた後に戻る
                await app(scope, receive, send)
            finally:
                with self._lock:
                    self._requests -= 1

        return tracked

    def begin_update(self) -> None:
        """再起動の途中か別の更新が動いていれば断り、更新のマーカーを起動する。"""
        with self._lock:
            # 再起動を始めた後か、別の更新が動いている: 断る
            if self._restarting or self._updating:
                raise RestartInProgressError(
                    "再起動の途中か、別の更新が動いています。"
                    "終わってから get_server_status で確認してください"
                )
            self._updating = True

    def end_update(self) -> None:
        """更新のマーカーを下ろす。`finish_update_and_restart` の後に呼んでも何もしない。"""
        with self._lock:
            self._updating = False

    def begin_restart(self) -> None:
        """再起動の途中か更新が動いていれば断り、再起動のマーカーを設定して停止を進めるタスクを作る。"""
        with self._lock:
            # 再起動を始めた後か、更新が動いている: 断る（更新は自分で再起動を始める）
            if self._restarting or self._updating:
                raise RestartInProgressError(
                    "再起動の途中か、更新が動いています。"
                    "再接続してから get_server_status で確認してください"
                )
            self._restarting = True
        self._start_stop()

    def finish_update_and_restart(self) -> None:
        """更新のマーカーを下ろすのと再起動のマーカーを設定するのを 1 回で行い、停止を進めるタスクを作る。"""
        with self._lock:
            # 更新のマーカーを設定している間は begin_restart が断るため、再起動のマーカーはまだ設定されていない
            self._updating = False
            self._restarting = True
        self._start_stop()

    def _enter(self) -> None:
        """再起動の途中なら断り、それ以外は処理中の数を 1 増やす。"""
        with self._lock:
            if self._restarting:
                raise RestartInProgressError(
                    "再起動の途中です。再接続してから get_server_status で確認してください"
                )
            self._in_flight += 1

    def _leave(self) -> None:
        """処理中の数を 1 減らす。"""
        with self._lock:
            self._in_flight -= 1

    def _start_stop(self) -> None:
        """停止を進めるタスクを、動いているイベントループに作る。"""
        self._stop_task = asyncio.get_running_loop().create_task(self._drain_and_stop())

    async def _drain_and_stop(self) -> None:
        """処理中の呼び出しと要求の終わりを上限まで待ち、待ち受けのサーバーに停止を合図する。"""
        try:
            async with asyncio.timeout(STOP_DRAIN_TIMEOUT):
                # 処理中の呼び出しか、応答を送信し終えていない要求が残っている間は待つ（新しい呼び出しは guard が断る）
                # should_exit を設定すると sse-starlette が送信中の応答をキャンセルするため、要求の応答の送信も待つ
                # 数は同期のツールのスレッドからも減るため、asyncio.Event でなく間隔を配置して見直す
                while self._in_flight > 0 or self._requests > 0:  # noqa: ASYNC110
                    await asyncio.sleep(DRAIN_POLL_INTERVAL)
        except TimeoutError:
            # 上限を過ぎた: 待つのをやめ、残った応答は sse-starlette がキャンセルする
            logger.warning(
                "再起動の停止の待ちが %s 秒を過ぎたため、処理中の呼び出し %d 件・要求 %d 件を待たずに止めます",
                STOP_DRAIN_TIMEOUT,
                self._in_flight,
                self._requests,
            )
        # uvicorn は次の周回で待ち受けを閉じて serve から返る。SSE のストリームは sse-starlette がキャンセルし、
        # SSE でない残りの接続は GRACEFUL_SHUTDOWN_TIMEOUT で切る
        if self._server is not None:
            self._server.should_exit = True
