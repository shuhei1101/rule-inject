"""単一ユースケース「MCPサーバーの設定を読み直す」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def test_normal(
    serve: Callable[..., Any],
    write_server_config: Callable[..., Path],
    make_rule: Callable[..., Path],
    tmp_path: Path,
    e2e_project: Path,
    server_config_path: Path,
) -> None:
    """直した設定ファイルを読めたことと、読んだ値を受け取る（正常シナリオ）。"""
    # 準備
    server = serve()
    rule = make_rule("added.md", "# added\n")
    index = tmp_path / "added.yaml"
    index.write_text(f"rules:\n  - rule: {rule}\n    paths: ['**/*.md']\n", encoding="utf-8")
    write_server_config(global_indexes=[index])
    # 実行
    result = server.call("reload_settings")
    listed = server.call("list_rules", project_dir=str(e2e_project), format="json")
    # 検証
    content = result.structured_content
    assert content["config_path"] == str(server_config_path)
    assert str(index) in content["indexes"]
    assert content["state_dir"]
    assert str(index) in listed.structured_content["indexes"]


def test_error_when_settings_unreadable(
    serve: Callable[..., Any],
    server_config_path: Path,
    tool_text: Callable[[Any], str],
) -> None:
    """読めない設定ファイルの場所と理由をツールのエラーで受け取り、サーバーは待ち受けたまま（異常シナリオ）。"""
    # 準備
    server = serve()
    with server_config_path.open("a", encoding="utf-8") as config:
        config.write("  unknown_key: 1\n")
    # 実行
    result = server.call("reload_settings")
    status = server.call("get_server_status")
    # 検証
    assert result.is_error is True
    assert str(server_config_path) in tool_text(result)
    assert "unknown_key" in tool_text(result)
    assert status.is_error is False
