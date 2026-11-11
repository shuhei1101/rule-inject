"""server/__main__.py の単体テスト。"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Any

import pytest
import uvicorn


@pytest.fixture
def run_spy(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """`uvicorn.Server.run` を、呼ばれたサーバーの設定を記録するだけの関数へ差し替える。"""
    calls: list[Any] = []

    def _run(self: uvicorn.Server, *args: Any, **kwargs: Any) -> None:
        """呼ばれたサーバーの設定を記録する（待ち受けない）。"""
        calls.append(self.config)

    monkeypatch.setattr(uvicorn.Server, "run", _run)
    return calls


@pytest.fixture
def execv_spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    """`os.execv` を、呼ばれた引数を記録するだけの関数へ差し替える。"""
    calls: list[tuple[str, list[str]]] = []

    def _execv(path: str, args: list[str]) -> None:
        """呼ばれた引数を記録する（プロセスを置き換えない）。"""
        calls.append((path, list(args)))

    monkeypatch.setattr(os, "execv", _execv)
    return calls


@pytest.fixture
def free_port_env(monkeypatch: pytest.MonkeyPatch) -> int:
    """設定ファイルを指さず、空いているポートを `RULE_INJECT_PORT` に配置する。"""
    with socket.create_server(("127.0.0.1", 0)) as probe:
        port = probe.getsockname()[1]
    monkeypatch.delenv("RULE_INJECT_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "/nonexistent-rule-inject-config")
    monkeypatch.setenv("RULE_INJECT_PORT", str(port))
    return port


def test_main_when_settings_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_spy: list[Any],
) -> None:
    """設定ファイルが読めなければ待ち受けずに終わる（異常系）。"""
    from rule_inject.server.__main__ import main

    # 準備
    config = tmp_path / "config" / "missing.yaml"
    monkeypatch.setenv("RULE_INJECT_CONFIG", str(config))
    monkeypatch.delenv("RULE_INJECT_PORT", raising=False)
    # 実行・検証
    with pytest.raises(SystemExit) as raised:
        main()
    assert raised.value.code == 1
    assert str(config) in capsys.readouterr().err
    assert run_spy == []


def test_main_when_port_in_use(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_spy: list[Any],
) -> None:
    """ポートが使用されていれば待ち受けずに終わる（異常系）。"""
    from rule_inject.server.__main__ import main

    # 準備
    monkeypatch.delenv("RULE_INJECT_CONFIG", raising=False)
    with socket.create_server(("127.0.0.1", 0)) as occupied:
        port = occupied.getsockname()[1]
        monkeypatch.setenv("RULE_INJECT_PORT", str(port))
        # 実行・検証
        with pytest.raises(SystemExit) as raised:
            main()
    assert raised.value.code == 1
    assert str(port) in capsys.readouterr().err
    assert run_spy == []


def test_main_when_restart_requested(
    monkeypatch: pytest.MonkeyPatch,
    free_port_env: int,
    run_spy: list[Any],
    execv_spy: list[tuple[str, list[str]]],
) -> None:
    """再起動で待ち受けを閉じたら同じプロセスで再起動する（正常系）。"""
    from rule_inject.server.__main__ import main
    from rule_inject.server.control import ServerControl

    # 準備
    monkeypatch.setattr(ServerControl, "restart_requested", property(lambda self: True))
    # 実行
    main()
    # 検証
    assert len(run_spy) == 1
    assert execv_spy == [(sys.executable, [sys.executable, "-m", "rule_inject.server"])]


def test_main_when_stopped(
    monkeypatch: pytest.MonkeyPatch,
    free_port_env: int,
    run_spy: list[Any],
    execv_spy: list[tuple[str, list[str]]],
) -> None:
    """Ctrl+C・SIGTERM で終わったときは再起動しない（正常系）。"""
    from rule_inject.server.__main__ import main
    from rule_inject.server.control import GRACEFUL_SHUTDOWN_TIMEOUT, ServerControl

    # 準備
    tracked: list[Any] = []

    def _track(self: ServerControl, app: Any) -> Any:
        """包んだことが分かるマーカーのアプリを返却する。"""
        wrapped = object()
        tracked.append(wrapped)
        return wrapped

    monkeypatch.setattr(ServerControl, "track", _track)
    # 実行
    main()
    # 検証
    assert execv_spy == []
    assert len(run_spy) == 1
    assert run_spy[0].timeout_graceful_shutdown == GRACEFUL_SHUTDOWN_TIMEOUT
    assert run_spy[0].port == free_port_env
    assert len(tracked) == 1
    assert run_spy[0].app is tracked[0]
