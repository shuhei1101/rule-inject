"""サーバーの稼働の状態（処理中の呼び出しの数・再起動と更新の印）と、再起動の停止の進め方。"""

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
    """待ち受けのポート・起動した時刻・処理中の呼び出しの数・再起動と更新の印を持ち、再起動の停止を進める。"""

    def __init__(self, *, port: int) -> None:
        """待ち受けているポートを受け、このプロセスのイメージで作った時刻を起動した時刻にする。"""
        self.port = port
        self.pid = os.getpid()
        self.started_at = datetime.now(UTC)
        # 同期のツールは SDK がスレッドで動かすため、数と印の読み書きを 1 つずつ行う
        self._lock = threading.Lock()
        self._in_flight = 0
        self._restarting = False
        self._updating = False
        self._server: uvicorn.Server | None = None
        # 停止を進めるタスク（参照を持って捨てられないようにする）
        self._stop_task: asyncio.Task[None] | None = None

    def attach(self, server: uvicorn.Server) -> None:
        """停止に使う `uvicorn.Server` を受け取る。"""
        self._server = server

    @property
    def restarting(self) -> bool:
        """再起動を始めたか。"""
        return self._restarting

    @property
    def restart_requested(self) -> bool:
        """`serve` が返った後に起動し直すか。Ctrl+C・SIGTERM で終わったときは偽。"""
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

    def begin_update(self) -> None:
        """再起動の途中か別の更新が動いていれば断り、更新の印を立てる。"""
        with self._lock:
            # 再起動を始めた後か、別の更新が動いている: 断る
            if self._restarting or self._updating:
                raise RestartInProgressError(
                    "再起動の途中か、別の更新が動いています。"
                    "終わってから get_server_status で確かめてください"
                )
            self._updating = True

    def end_update(self) -> None:
        """更新の印を下ろす。`finish_update_and_restart` の後に呼んでも何もしない。"""
        with self._lock:
            self._updating = False

    def begin_restart(self) -> None:
        """再起動の途中か更新が動いていれば断り、再起動の印を立てて停止を進めるタスクを作る。"""
        with self._lock:
            # 再起動を始めた後か、更新が動いている: 断る（更新は自分で再起動を始める）
            if self._restarting or self._updating:
                raise RestartInProgressError(
                    "再起動の途中か、更新が動いています。"
                    "接続し直してから get_server_status で確かめてください"
                )
            self._restarting = True
        self._start_stop()

    def finish_update_and_restart(self) -> None:
        """更新の印を下ろすのと再起動の印を立てるのを 1 回で行い、停止を進めるタスクを作る。"""
        with self._lock:
            # 更新の印を立てている間は begin_restart が断るため、再起動の印はまだ立っていない
            self._updating = False
            self._restarting = True
        self._start_stop()

    def _enter(self) -> None:
        """再起動の途中なら断り、それ以外は処理中の数を 1 増やす。"""
        with self._lock:
            if self._restarting:
                raise RestartInProgressError(
                    "再起動の途中です。接続し直してから get_server_status で確かめてください"
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
        """処理中の呼び出しの終わりを上限まで待ち、待ち受けのサーバーに停止を合図する。"""
        try:
            async with asyncio.timeout(STOP_DRAIN_TIMEOUT):
                # 処理中の呼び出しが残っている間は待つ（新しい呼び出しは guard が断る）
                while self._in_flight > 0:
                    await asyncio.sleep(DRAIN_POLL_INTERVAL)
        except TimeoutError:
            # 上限を過ぎた: 待つのをやめ、残った呼び出しは uvicorn が上限で切る
            logger.warning(
                "再起動の停止の待ちが %s 秒を過ぎたため、処理中の %d 件を待たずに止めます",
                STOP_DRAIN_TIMEOUT,
                self._in_flight,
            )
        # uvicorn は次の周回で待ち受けを閉じ、残った接続を GRACEFUL_SHUTDOWN_TIMEOUT で切って serve から返る
        if self._server is not None:
            self._server.should_exit = True
