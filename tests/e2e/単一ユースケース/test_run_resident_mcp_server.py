"""単一ユースケース「MCPサーバーを常駐させる」の E2E テスト。"""

from __future__ import annotations

import signal
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

LOOPBACK_HEX = "0100007F"
SIGTERM_EXIT_CODES = (128 + signal.SIGTERM, -signal.SIGTERM)
STOP_TIMEOUT_SEC = 20
SERVER_NAME = "rule-inject"


def test_normal(
    free_port: Callable[[], int],
    write_server_config: Callable[..., Path],
    resident_server: Callable[..., Any],
    addresses_listening: Callable[[int], set[str]],
    run_claude_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """起動したサーバーが設定ファイルのポートだけで待ち受け、登録した Claude Code から接続できる（正常シナリオ）。"""
    # 準備
    port = free_port()
    write_server_config(port)
    server = resident_server(port)
    # 実行
    added = run_claude_cli(
        "mcp", "add", "--transport", "http", "-s", "user", SERVER_NAME, server.url
    )
    listed = run_claude_cli("mcp", "list")
    # 検証
    assert addresses_listening(port) == {LOOPBACK_HEX}
    assert added.returncode == 0
    assert SERVER_NAME in listed.stdout
    assert "Connected" in listed.stdout
    assert "Failed" not in listed.stdout


def test_normal_when_stopped(
    free_port: Callable[[], int],
    write_server_config: Callable[..., Path],
    resident_server: Callable[..., Any],
    port_is_listening: Callable[[int], bool],
) -> None:
    """SIGTERM で待ち受けを閉じて終わる（正常シナリオ）。"""
    # 準備
    port = free_port()
    write_server_config(port)
    server = resident_server(port)
    # 実行
    server.process.send_signal(signal.SIGTERM)
    server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode in SIGTERM_EXIT_CODES
    assert "Application shutdown complete." in server.stderr_text()
    assert port_is_listening(port) is False


def test_error_when_port_in_use(
    free_port: Callable[[], int],
    write_server_config: Callable[..., Path],
    resident_server: Callable[..., Any],
) -> None:
    """ポートが使われているとき、理由を書いて 0 以外の終了コードで終わる（異常シナリオ）。"""
    # 準備
    port = free_port()
    write_server_config(port)
    with socket.create_server(("127.0.0.1", port)):
        # 実行
        server = resident_server(port, wait_ready=False)
        server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert str(port) in server.stderr_text()


def test_error_when_settings_unreadable(
    free_port: Callable[[], int],
    write_server_config: Callable[..., Path],
    resident_server: Callable[..., Any],
) -> None:
    """設定ファイルが読めないとき、場所と理由を書いて 0 以外の終了コードで終わり、待ち受けない（異常シナリオ）。"""
    # 準備
    port = free_port()
    config = write_server_config(port)
    config.write_text(f"global:\n  server_port: {port}\n  foo: 1\n", encoding="utf-8")
    # 実行
    server = resident_server(port, wait_ready=False)
    server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert str(config) in server.stderr_text()
    assert "foo" in server.stderr_text()
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=0.5)
