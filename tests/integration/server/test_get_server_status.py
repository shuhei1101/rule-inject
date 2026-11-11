"""インターフェース定義『サーバーの状態の確認』の結合テスト。"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

# 作業ツリーの直下（`python -m rule_inject.server` がクローンとして見つける場所）
REPO_ROOT = Path(__file__).resolve().parents[3]


def test_normal(start_server: Callable[..., Any], config_text: Callable[..., str]) -> None:
    """待ち受けのポート・プロセス・起動した時刻・バージョン・クローンの commit・設定ファイルを返却する（正常系）。"""
    # 準備
    server = start_server(config_text)
    version = (REPO_ROOT / "version.ini").read_text(encoding="utf-8").splitlines()[0].strip()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    # 実行
    result = server.call("get_server_status")
    # 検証
    content = result.structured_content
    assert result.is_error is False
    assert content["port"] == server.port
    assert content["pid"] == server.process.pid
    assert content["version"] == version
    assert content["commit"] == head
    assert content["clone"] == str(REPO_ROOT)
    assert content["config"] == {
        "path": str(server.config_path),
        "readable": True,
        "error": None,
    }
    assert content["restarting"] is False


def test_normal_when_settings_unreadable(
    shared_server: Any, invalid_config: Callable[[], str]
) -> None:
    """設定ファイルが読めなくてもエラーにせず、読めない理由を記載して返却する（正常系）。"""
    # 準備
    config = invalid_config()
    # 実行
    result = shared_server.call("get_server_status")
    # 検証
    content = result.structured_content
    assert result.is_error is False
    assert content["port"] == shared_server.port
    assert content["version"]
    assert content["config"]["readable"] is False
    assert config in content["config"]["error"]
    assert "foo" in content["config"]["error"]


def test_normal_when_not_git_clone(tmp_path: Path) -> None:
    """commit を取得できないときは `commit` を `null` にして返却する（正常系）。"""
    from rule_inject.server.app import build_server
    from rule_inject.server.control import ServerControl

    # 準備
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / "version.ini").write_text("v9.9.9\n", encoding="utf-8")
    server = build_server({}, control=ServerControl(port=8783), clone=clone)
    # 実行
    result = asyncio.run(server.call_tool("get_server_status", {}))
    assert isinstance(result, CallToolResult)
    # 検証
    content = result.structured_content
    assert result.is_error is False
    assert content["commit"] is None
    assert content["version"] == "v9.9.9"
