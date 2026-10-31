"""単一ユースケース「MCPサーバーを常駐させる」の E2E テスト。"""

from __future__ import annotations

import signal
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

LOOPBACK_HEX = "0100007F"
SIGTERM_EXIT_CODES = (128 + signal.SIGTERM, -signal.SIGTERM)
STOP_TIMEOUT_SEC = 20
SERVER_NAME = "rule-inject"


def test_normal(
    write_server_config: Callable[..., Path],
    resident_server: Callable[..., Any],
    addresses_listening: Callable[[int], set[str]],
    run_claude_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """起動したサーバーが設定ファイルのポートだけで待ち受け、登録した Claude Code から接続できる（正常シナリオ）。"""
    # 準備
    server = resident_server(write_server_config)
    # 実行
    added = run_claude_cli(
        "mcp", "add", "--transport", "http", "-s", "user", SERVER_NAME, server.url
    )
    listed = run_claude_cli("mcp", "list")
    # 検証
    assert addresses_listening(server.port) == {LOOPBACK_HEX}
    assert added.returncode == 0
    assert SERVER_NAME in listed.stdout
    assert "Connected" in listed.stdout
    assert "Failed" not in listed.stdout


def test_normal_when_stopped(
    write_server_config: Callable[..., Path],
    resident_server: Callable[..., Any],
) -> None:
    """SIGTERM で待ち受けを閉じて終わる（正常シナリオ）。"""
    # 準備
    server = resident_server(write_server_config)
    # 実行
    server.process.send_signal(signal.SIGTERM)
    server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode in SIGTERM_EXIT_CODES
    assert "Application shutdown complete." in server.stderr_text()
    assert "Finished server process" in server.stderr_text()


def test_error_when_port_in_use(
    write_server_config: Callable[..., Path],
    resident_server: Callable[..., Any],
) -> None:
    """ポートが使われているとき、理由を書いて 0 以外の終了コードで終わる（異常シナリオ）。"""
    # 準備: テストがポート 0 で待ち受け、そのポートを設定ファイルに書く
    with socket.create_server(("127.0.0.1", 0)) as held:
        port = int(held.getsockname()[1])
        # 実行
        server = resident_server(lambda _port: write_server_config(port), wait_ready=False)
        server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert str(port) in server.stderr_text()


def test_error_when_settings_unreadable(
    server_config_path: Path,
    resident_server: Callable[..., Any],
) -> None:
    """設定ファイルが読めないとき、場所と理由を書いて 0 以外の終了コードで終わり、待ち受けない（異常シナリオ）。"""
    # 実行
    server = resident_server(
        lambda port: server_config_path.write_text(
            f"global:\n  server_port: {port}\n  foo: 1\n", encoding="utf-8"
        ),
        wait_ready=False,
    )
    server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert "Uvicorn running on" not in server.stderr_text()
    assert str(server_config_path) in server.stderr_text()
    assert "foo" in server.stderr_text()
