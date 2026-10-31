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
    "list_rules",
    "search_rules",
    "write_index_entry",
]
HOST = "127.0.0.1"
LOOPBACK_HEX = "0100007F"
SIGTERM_EXIT_CODES = (128 + signal.SIGTERM, -signal.SIGTERM)
STOP_TIMEOUT_SEC = 15
# 起動して失敗で終わるまでの上限（子プロセスの起動を含むため、起動を待つ上限と揃える）
EXIT_TIMEOUT_SEC = 30


def test_normal(
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
    addresses_listening: Callable[[int], set[str]],
) -> None:
    """設定ファイルのポートで待ち受け、MCP のクライアントから接続できる（正常系）。"""
    # 実行
    server = start_server(config_text)
    # 検証
    assert addresses_listening(server.port) == {LOOPBACK_HEX}
    assert sorted(server.tool_names()) == TOOL_NAMES


def test_normal_when_port_overridden(
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
    addresses_listening: Callable[[int], set[str]],
) -> None:
    """設定ファイルのポートを他が待ち受けていても、`RULE_INJECT_PORT` のポートで待ち受ける（正常系）。"""
    # 準備: 設定ファイルのポートは、確かめ終わるまでテストが待ち受けたままにする
    # （上書きが効かずに設定ファイルのポートを使おうとすると、使われているとして起動に失敗する）
    with socket.create_server((HOST, 0)) as held:
        config_port = int(held.getsockname()[1])
        # 実行
        server = start_server(lambda _port: config_text(config_port), port_env=True)
        # 検証
        assert server.port != config_port
        assert addresses_listening(server.port) == {LOOPBACK_HEX}
        assert sorted(server.tool_names()) == TOOL_NAMES


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
    """ポートが使われているとき、待ち受けに失敗し、理由を書いて終わる（異常系）。"""
    # 準備: テストがポート 0 で待ち受け、そのポートを設定ファイルに書く
    with socket.create_server((HOST, 0)) as held:
        port = int(held.getsockname()[1])
        # 実行
        server = start_server(lambda _port: config_text(port), wait_ready=False)
        server.process.wait(timeout=EXIT_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert str(port) in server.stderr_text()
    assert "別のプロセスが使っている" in server.stderr_text()


def test_error_when_settings_unreadable(
    start_server: Callable[..., Any],
    config_path: Path,
) -> None:
    """設定ファイルが読めないとき、待ち受ける前に理由を書いて終わる（異常系）。"""
    # 実行
    server = start_server(
        lambda port: f"global:\n  server_port: {port}\n  foo: 1\n", wait_ready=False
    )
    server.process.wait(timeout=EXIT_TIMEOUT_SEC)
    # 検証
    assert server.process.returncode != 0
    assert "Uvicorn running on" not in server.stderr_text()
    assert str(config_path) in server.stderr_text()
    assert "foo" in server.stderr_text()
