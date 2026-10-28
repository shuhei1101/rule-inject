"""インターフェース定義『索引のチェック』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult


def test_normal_when_no_violation(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """問題の無い索引で `problem_count` が 0 になる（正常系）。"""
    # 準備
    first = make_index("# a\n", "rules/a.md")
    second = make_index("# b\n", "rules/b.md")
    index = make_index(
        f'rules:\n  - rule: {first}\n    paths: ["**/*.py"]\n  - rule: {second}\n    on: [write]\n'
    )
    server = running_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    assert content["problem_count"] == 0
    assert content["indexes"][0]["index"] == str(index)
    assert content["indexes"][0]["hook_error"] is None
    assert content["indexes"][0]["violations"] == []
    assert content["indexes"][0]["missing_rules"] == []
    assert content["indexes"][0]["skipped_entries"] == []
    assert content["config_path"] == str(server.config_path)


def test_normal_when_schema_violated(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """フックは読めるが Schema に違反するエントリの場所と理由を返す（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n    paths: []\n  - rule: {rule}\n")
    server = running_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    report = result.structured_content["indexes"][0]
    assert report["violations"][0]["location"] == "rules[0].paths"
    assert report["violations"][0]["reason"]
    assert report["hook_error"] is None


def test_normal_when_unreadable_by_hook(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """フックが読めない索引は理由だけを返し、Schema には照らさない（正常系）。"""
    # 準備
    index = make_index("rules:\n  - rule: /r/a.md\n    paths: [a,\n      b]\n")
    server = running_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    report = result.structured_content["indexes"][0]
    assert "行目" in report["hook_error"]
    assert report["violations"] == []
    assert report["missing_rules"] == []


def test_normal_when_rule_file_missing(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """ルールの場所にファイルが無いエントリを返す（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n  - rule: {tmp_path}/rules/missing.md\n")
    server = running_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    assert content["indexes"][0]["missing_rules"] == [
        {"position": 1, "rule": f"{tmp_path}/rules/missing.md"}
    ]
    assert content["problem_count"] == 1


def test_error_when_project_dir_not_absolute(
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """相対パスの `project_dir` をエラーにする（異常系）。"""
    # 準備
    server = running_server(make_index("rules: []\n"))
    # 実行
    result = server.call("check_indexes", project_dir="project", format="json")
    # 検証
    assert result.is_error is True
    assert "絶対パス" in text_of(result)


def test_error_when_settings_unreadable(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    invalid_config: Callable[[], str],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """呼び出しの時点で読めない設定ファイルをエラーにする（異常系）。"""
    # 準備
    server = running_server(make_index("rules: []\n"))
    config = invalid_config()
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    assert result.is_error is True
    assert config in text_of(result)
    assert "foo" in text_of(result)
