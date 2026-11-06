"""単一ユースケース「MCPサーバーの状態を確認する」の E2E テスト。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

# このリポジトリの直下（`python -m rule_inject.server` がクローンとして見つける場所）
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_normal(serve: Callable[..., Any], server_config_path: Path) -> None:
    """待ち受けのポート・プロセス・バージョン・クローンの commit・設定ファイルを受け取る（正常シナリオ）。"""
    # 準備
    server = serve()
    version = (REPO_ROOT / "version.ini").read_text(encoding="utf-8").splitlines()[0].strip()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    # 実行
    result = server.call("get_server_status")
    # 検証
    content = result.structured_content
    assert content["port"] == server.port
    assert content["pid"] == server.process.pid
    assert content["version"] == version
    assert content["commit"] == head
    assert content["config"]["path"] == str(server_config_path)
    assert content["config"]["readable"] is True


def test_normal_when_settings_unreadable(
    serve: Callable[..., Any], server_config_path: Path
) -> None:
    """設定ファイルが読めなくても、状態と読めない理由を受け取る（正常シナリオ）。"""
    # 準備
    server = serve()
    with server_config_path.open("a", encoding="utf-8") as config:
        config.write("  unknown_key: 1\n")
    # 実行
    result = server.call("get_server_status")
    # 検証
    content = result.structured_content
    assert result.is_error is False
    assert content["port"] == server.port
    assert content["pid"] == server.process.pid
    assert content["version"]
    assert content["config"]["readable"] is False
    assert "unknown_key" in content["config"]["error"]
