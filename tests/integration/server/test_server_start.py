"""インターフェース定義『サーバーの起動』の結合テスト。"""

from __future__ import annotations

import signal
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

TOOL_NAMES = [
    "check_indexes",
    "delete_index_entry",
    "delete_read_records",
    "get_read_records",
    "get_server_status",
    "list_rules",
    "reload_settings",
    "restart_server",
    "search_rules",
    "update_server",
    "write_index_entry",
]
HOST = "127.0.0.1"
LOOPBACK_HEX = "0100007F"
SIGTERM_EXIT_CODES = (128 + signal.SIGTERM, -signal.SIGTERM)
STOP_TIMEOUT_SEC = 15
# 起動して失敗で終わるまでを待つ上限（導き方はテスト実行方法の結合テスト（バック）の補足「起動を待つ上限」）
EXIT_TIMEOUT_SEC = 51


def test_normal(
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
    addresses_listening: Callable[[int], set[str]],
) -> None:
    """`RULE_INJECT_PORT` のポートで待ち受け、MCP のクライアントから接続できる（正常系）。"""
    # 実行
    server = start_server(config_text)
    # 検証
    assert addresses_listening(server.port) == {LOOPBACK_HEX}
    assert sorted(server.tool_names()) == TOOL_NAMES
    instructions = server.instructions()
    assert instructions is not None
    assert len(instructions) <= 4096
    assert "Write" in instructions
    assert "空の内容" in instructions
    assert "Edit" in instructions
    assert "list_rules" in instructions
    assert "search_rules" in instructions
    assert "check_indexes" in instructions
    assert "Read" in instructions
    assert "grep" in instructions


def test_normal_when_stopped(
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
) -> None:
    """SIGTERM で待ち受けを閉じて終わる（正常系）。"""
    # 準備
    server = start_server(config_text)
    # 実行
    server.process.send_signal(signal.SIGTERM)
    server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode in SIGTERM_EXIT_CODES
    assert "Application shutdown complete." in server.stderr_text()
    assert "Finished server process" in server.stderr_text()


def test_error_when_port_in_use(
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
) -> None:
    """ポートが使用中のとき、待ち受けに失敗し、理由を記載して終わる（異常系）。"""
    # 準備: テストがポート 0 で待ち受け、そのポートを `RULE_INJECT_PORT` に指定する
    with socket.create_server((HOST, 0)) as held:
        port = int(held.getsockname()[1])
        # 実行
        server = start_server(config_text, port=port, wait_ready=False)
        server.process.wait(timeout=EXIT_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert str(port) in server.stderr_text()
    assert "別のプロセスが使用している" in server.stderr_text()


def test_error_when_settings_unreadable(
    start_server: Callable[..., Any],
    config_path: Path,
) -> None:
    """設定ファイルが読めないとき、待ち受ける前に理由を記載して終わる（異常系）。"""
    # 実行
    server = start_server(lambda: "global:\n  foo: 1\n", wait_ready=False)
    server.process.wait(timeout=EXIT_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert "Uvicorn running on" not in server.stderr_text()
    assert str(config_path) in server.stderr_text()
    assert "foo" in server.stderr_text()


def test_error_when_removed_key(
    start_server: Callable[..., Any],
    config_path: Path,
) -> None:
    """`global.server_port` が残った設定ファイルでは待ち受けず、移し替えの案内を出して終わる（異常系）。"""
    # 実行
    server = start_server(lambda: "global:\n  server_port: 9000\n", wait_ready=False)
    server.process.wait(timeout=EXIT_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert str(config_path) in server.stderr_text()
    assert "global.server_port" in server.stderr_text()
    assert "global-setup" in server.stderr_text()
