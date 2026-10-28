"""server/__main__.py の単体テスト。"""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver import MCPServer


@pytest.fixture
def run_spy(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    """`MCPServer.run` を、呼ばれた引数を控えるだけの関数へ差し替える。"""
    calls: list[tuple[Any, ...]] = []

    def _run(self: MCPServer, *args: Any, **kwargs: Any) -> None:
        """呼ばれたことを控える（待ち受けない）。"""
        calls.append((args, kwargs))

    monkeypatch.setattr(MCPServer, "run", _run)
    return calls


def test_main_when_settings_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_spy: list[tuple[Any, ...]],
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
    run_spy: list[tuple[Any, ...]],
) -> None:
    """ポートが使われていれば待ち受けずに終わる（異常系）。"""
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
