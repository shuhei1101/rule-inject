"""インターフェース定義『サーバーの起動』の結合テスト。"""

from __future__ import annotations

import signal
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

TOOL_NAMES = [
    "check_indexes",
    "delete_index_entry",
    "delete_read_records",
    "get_read_records",
    "list_rules",
    "search_rules",
    "write_index_entry",
]
LOOPBACK_HEX = "0100007F"
SIGTERM_EXIT_CODES = (128 + signal.SIGTERM, -signal.SIGTERM)
STOP_TIMEOUT_SEC = 15


def test_normal(
    free_port: Callable[[], int],
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
    addresses_listening: Callable[[int], set[str]],
) -> None:
    """設定ファイルのポートで待ち受け、MCP のクライアントから接続できる（正常系）。"""
    # 準備
    port = free_port()
    # 実行
    server = start_server(config_text(port), port=port)
    # 検証
    assert addresses_listening(port) == {LOOPBACK_HEX}
    assert sorted(server.tool_names()) == TOOL_NAMES


def test_normal_when_port_overridden(
    free_port: Callable[[], int],
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
    addresses_listening: Callable[[int], set[str]],
    port_is_listening: Callable[[int], bool],
) -> None:
    """`RULE_INJECT_PORT` のポートで待ち受ける（正常系）。"""
    # 準備
    config_port = free_port()
    override_port = free_port()
    # 実行
    server = start_server(
        config_text(config_port),
        port=override_port,
        extra_env={"RULE_INJECT_PORT": str(override_port)},
    )
    # 検証
    assert addresses_listening(override_port) == {LOOPBACK_HEX}
    assert port_is_listening(config_port) is False
    assert sorted(server.tool_names()) == TOOL_NAMES


def test_normal_when_stopped(
    free_port: Callable[[], int],
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
    port_is_listening: Callable[[int], bool],
) -> None:
    """SIGTERM で待ち受けを閉じて終わる（正常系）。"""
    # 準備
    port = free_port()
    server = start_server(config_text(port), port=port)
    # 実行
    server.process.send_signal(signal.SIGTERM)
    server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode in SIGTERM_EXIT_CODES
    assert "Application shutdown complete." in server.stderr_text()
    assert port_is_listening(port) is False


def test_error_when_port_in_use(
    free_port: Callable[[], int],
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
) -> None:
    """ポートが使われているとき、待ち受けに失敗し、理由を書いて終わる（異常系）。"""
    # 準備
    port = free_port()
    with socket.create_server(("127.0.0.1", port)):
        # 実行
        server = start_server(config_text(port), port=port, wait_ready=False)
        server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert str(port) in server.stderr_text()


def test_error_when_settings_unreadable(
    free_port: Callable[[], int],
    start_server: Callable[..., Any],
    config_path: Path,
) -> None:
    """設定ファイルが読めないとき、待ち受ける前に理由を書いて終わる（異常系）。"""
    # 準備
    port = free_port()
    text = f"global:\n  server_port: {port}\n  foo: 1\n"
    # 実行
    server = start_server(text, port=port, wait_ready=False)
    server.process.wait(timeout=STOP_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert str(config_path) in server.stderr_text()
    assert "foo" in server.stderr_text()
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=0.5)
