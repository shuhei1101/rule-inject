"""server/control.py の単体テスト。"""

from __future__ import annotations

import asyncio
import time
from collections.abc import MutableMapping
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

PORT = 8783


def _fake_server() -> Any:
    """`should_exit` だけを持つ `uvicorn.Server` の代わり。"""
    return SimpleNamespace(should_exit=False)


def test_guard() -> None:
    """呼び出しの間だけ処理中の数が増える（正常系）。"""
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=PORT)
    seen: list[int] = []

    def sync_tool(value: int) -> int:
        """処理中の数を記録して値を返却する。"""
        seen.append(control._in_flight)
        return value

    async def async_tool(value: int) -> int:
        """処理中の数を記録して値を返却する。"""
        seen.append(control._in_flight)
        return value

    # 実行
    sync_result = control.guard(sync_tool)(1)
    async_result = asyncio.run(control.guard(async_tool)(2))
    # 検証
    assert sync_result == 1
    assert async_result == 2
    assert seen == [1, 1]
    assert control._in_flight == 0


def test_guard_when_restarting() -> None:
    """再起動を始めた後は断る（異常系）。"""
    from rule_inject.server.control import RestartInProgressError, ServerControl

    # 準備
    control = ServerControl(port=PORT)
    control.attach(_fake_server())
    called: list[int] = []

    def tool() -> None:
        """呼ばれたことを記録する。"""
        called.append(1)

    async def scenario() -> None:
        """イベントループの中で再起動を始め、包んだ関数を呼ぶ。"""
        control.begin_restart()
        control.guard(tool)()

    # 実行・検証
    with pytest.raises(RestartInProgressError, match="再起動の途中"):
        asyncio.run(scenario())
    assert called == []


def test_guard_when_raises() -> None:
    """包んだ関数が例外を送出しても処理中の数を戻す（異常系）。"""
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=PORT)

    def tool() -> None:
        """ToolError を送出する。"""
        raise ToolError("失敗")

    # 実行・検証
    with pytest.raises(ToolError, match="失敗"):
        control.guard(tool)()
    assert control._in_flight == 0


def test_begin_update_when_updating() -> None:
    """更新の途中の 2 回目を断る（異常系）。"""
    from rule_inject.server.control import RestartInProgressError, ServerControl

    # 準備
    control = ServerControl(port=PORT)
    control.begin_update()
    # 実行・検証
    with pytest.raises(RestartInProgressError, match="更新"):
        control.begin_update()


def test_begin_restart_when_restarting() -> None:
    """再起動の途中の 2 回目を断る（異常系）。"""
    from rule_inject.server.control import RestartInProgressError, ServerControl

    # 準備
    control = ServerControl(port=PORT)
    control.attach(_fake_server())
    errors: list[str] = []

    async def scenario() -> int:
        """再起動を 2 回始め、作られたタスクの数を返却する。"""
        control.begin_restart()
        try:
            control.begin_restart()
        except RestartInProgressError as exc:
            errors.append(str(exc))
        return len(asyncio.all_tasks()) - 1

    # 実行
    task_count = asyncio.run(scenario())
    # 検証
    assert len(errors) == 1
    assert "再起動の途中" in errors[0]
    assert task_count == 1


def test_begin_restart_when_updating() -> None:
    """更新の途中の再起動を断る（異常系）。"""
    from rule_inject.server.control import RestartInProgressError, ServerControl

    # 準備
    control = ServerControl(port=PORT)
    control.attach(_fake_server())
    control.begin_update()
    errors: list[str] = []

    async def scenario() -> int:
        """更新の途中に再起動を始め、作られたタスクの数を返却する。"""
        try:
            control.begin_restart()
        except RestartInProgressError as exc:
            errors.append(str(exc))
        return len(asyncio.all_tasks()) - 1

    # 実行
    task_count = asyncio.run(scenario())
    # 検証
    assert len(errors) == 1
    assert "更新" in errors[0]
    assert control.restarting is False
    assert task_count == 0


def test_finish_update_and_restart() -> None:
    """更新の途中から再起動を始める（正常系）。"""
    from rule_inject.server.control import RestartInProgressError, ServerControl

    # 準備
    control = ServerControl(port=PORT)
    control.attach(_fake_server())
    control.begin_update()

    async def scenario() -> int:
        """更新を終えて再起動を始め、作られたタスクの数を返却する。"""
        control.finish_update_and_restart()
        return len(asyncio.all_tasks()) - 1

    # 実行
    task_count = asyncio.run(scenario())
    # 検証
    assert control.restarting is True
    assert control.restart_requested is True
    assert task_count == 1
    with pytest.raises(RestartInProgressError):
        control.begin_update()


def test_drain_and_stop() -> None:
    """処理中の呼び出しが終わってから止める（正常系）。"""
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=PORT)
    server = _fake_server()
    control.attach(server)
    observed: list[bool] = []

    async def slow_tool() -> None:
        """0.3 秒かかる呼び出し。途中で止める合図が出ていないかを記録する。"""
        await asyncio.sleep(0.3)
        observed.append(server.should_exit)

    async def scenario() -> None:
        """処理中の呼び出しがある間に再起動を始め、停止のタスクの終わりを待つ。"""
        call = asyncio.create_task(control.guard(slow_tool)())
        await asyncio.sleep(0.05)
        control.begin_restart()
        await call
        assert control._stop_task is not None
        await control._stop_task

    # 実行
    asyncio.run(scenario())
    # 検証
    assert observed == [False]
    assert server.should_exit is True


def test_drain_and_stop_when_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """上限を過ぎたら待つのをやめて止める（正常系）。"""
    from rule_inject.server import control as control_module
    from rule_inject.server.control import ServerControl

    # 準備
    monkeypatch.setattr(control_module, "STOP_DRAIN_TIMEOUT", 0.2)
    control = ServerControl(port=PORT)
    server = _fake_server()
    control.attach(server)

    async def endless_tool() -> None:
        """終わらない呼び出し。"""
        await asyncio.sleep(60)

    async def scenario() -> float:
        """終わらない呼び出しを処理中にしたまま再起動を始め、止まるまでの秒数を返却する。"""
        call = asyncio.create_task(control.guard(endless_tool)())
        await asyncio.sleep(0.05)
        started = time.monotonic()
        control.begin_restart()
        assert control._stop_task is not None
        await control._stop_task
        elapsed = time.monotonic() - started
        call.cancel()
        return elapsed

    # 実行
    elapsed = asyncio.run(scenario())
    # 検証
    assert server.should_exit is True
    assert 0.15 <= elapsed < 1.0


def _http_scope(method: str) -> dict[str, Any]:
    """`/mcp` への HTTP の要求の `scope`。"""
    return {"type": "http", "method": method, "path": "/mcp"}


async def _receive() -> dict[str, Any]:
    """要求の本文を持たない `receive`。"""
    return {"type": "http.request", "body": b"", "more_body": False}


async def _call(app: Any, method: str, send: Any) -> None:
    """ASGI のアプリを `/mcp` への要求で呼ぶ。"""
    await app(_http_scope(method), _receive, send)


def test_drain_and_stop_when_request_in_flight() -> None:
    """要求の応答を送信し終えてから止める（正常系）。"""
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=PORT)
    server = _fake_server()
    control.attach(server)
    observed: list[bool] = []
    sent: list[MutableMapping[str, Any]] = []

    async def slow_app(scope: Any, receive: Any, send: Any) -> None:
        """0.3 秒待ってから応答を送信する。送信の前に止める合図が出ていないかを記録する。"""
        await asyncio.sleep(0.3)
        observed.append(server.should_exit)
        await send({"type": "http.response.body", "body": b"done", "more_body": False})

    async def send(message: MutableMapping[str, Any]) -> None:
        """送信した応答を記録する。"""
        sent.append(message)

    async def scenario() -> None:
        """要求の応答を送信している間に再起動を始め、停止のタスクの終わりを待つ。"""
        request = asyncio.create_task(_call(control.track(slow_app), "POST", send))
        await asyncio.sleep(0.05)
        control.begin_restart()
        await request
        assert control._stop_task is not None
        await control._stop_task

    # 実行
    asyncio.run(scenario())
    # 検証
    assert observed == [False]
    assert len(sent) == 1
    assert server.should_exit is True


def test_track() -> None:
    """POST の要求の応答を送信し終えるまでだけ数える（正常系）。"""
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=PORT)
    seen: list[int] = []
    sent: list[MutableMapping[str, Any]] = []
    response = {"type": "http.response.body", "body": b"ok", "more_body": False}

    async def app(scope: Any, receive: Any, send: Any) -> None:
        """処理中の要求の数を記録してから応答を送信する。"""
        await asyncio.sleep(0.05)
        seen.append(control._requests)
        await send(response)

    async def send(message: MutableMapping[str, Any]) -> None:
        """送信した応答を記録する。"""
        sent.append(message)

    # 実行
    asyncio.run(_call(control.track(app), "POST", send))
    # 検証
    assert seen == [1]
    assert control._requests == 0
    assert sent == [response]


def test_track_when_get() -> None:
    """GET の要求は数えない（正常系）。"""
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=PORT)
    seen: list[int] = []

    async def app(scope: Any, receive: Any, send: Any) -> None:
        """処理中の要求の数を記録する。"""
        seen.append(control._requests)

    async def send(message: MutableMapping[str, Any]) -> None:
        """何もしない。"""

    # 実行
    asyncio.run(_call(control.track(app), "GET", send))
    # 検証
    assert seen == [0]
    assert control._requests == 0


def test_track_when_raises() -> None:
    """包んだアプリが例外を送出しても数を戻す（異常系）。"""
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=PORT)

    async def app(scope: Any, receive: Any, send: Any) -> None:
        """RuntimeError を送出する。"""
        raise RuntimeError("失敗")

    async def send(message: MutableMapping[str, Any]) -> None:
        """何もしない。"""

    # 実行・検証
    with pytest.raises(RuntimeError, match="失敗"):
        asyncio.run(_call(control.track(app), "POST", send))
    assert control._requests == 0
