"""単一ユースケース「効いているルールの一覧を見る」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult


def _indexes(
    tmp_path: Path, make_text_file: Callable[..., Path], make_rule: Callable[..., Path]
) -> tuple[Path, Path, Path, Path]:
    """ユーザーの索引とプロジェクトの索引（それぞれ有効なエントリが 1 つ）と、そのルールの本文を置く。"""
    user_rule = make_rule("user.md", "# user\n")
    project_rule = make_rule("project.md", "# project\n")
    user = make_text_file(
        "user/rules.yaml",
        f'rules:\n  - rule: {user_rule}\n    paths: ["**/*.md"]\n    on: [read]\n',
    )
    project = make_text_file(
        "project_rules/rules.yaml",
        f'rules:\n  - rule: {project_rule}\n    paths: ["**/*.py"]\n    on: [write]\n',
    )
    return user, project, user_rule, project_rule


def test_normal(
    tmp_path: Path,
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    server_config_path: Path,
    serve: Callable[..., Any],
) -> None:
    """ユーザーの索引とプロジェクトの索引のエントリを、フックが読む順に受け取る（正常シナリオ）。"""
    # 準備
    user, project, user_rule, project_rule = _indexes(tmp_path, make_text_file, make_rule)
    server = serve(project, global_indexes=[user])
    # 実行
    result = server.call("list_rules", project_dir=str(e2e_project), format="json")
    # 検証
    content = result.structured_content
    assert content["config_path"] == str(server_config_path)
    assert content["indexes"] == [str(user), str(project)]
    assert [entry["rule"] for entry in content["entries"]] == [str(user_rule), str(project_rule)]
    assert content["entries"][0]["paths"] == ["**/*.md"]
    assert content["entries"][0]["on"] == ["read"]
    assert content["entries"][1]["paths"] == ["**/*.py"]
    assert content["entries"][1]["on"] == ["write"]


def test_normal_when_some_entries_excluded(
    tmp_path: Path,
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """読めない索引・読み飛ばしたエントリ・無効のエントリを理由とともに受け取る（正常シナリオ）。"""
    # 準備
    user, _, _, project_rule = _indexes(tmp_path, make_text_file, make_rule)
    off_rule = make_rule("off.md", "# off\n")
    project = make_text_file(
        "project_rules/rules.yaml",
        f"rules:\n  - rule: {project_rule}\n"
        '  - rule: "!{RULE_INJECT_E2E_UNSET_NAME}/a.md"\n'
        f"  - rule: {off_rule}\n    enabled: false\n",
    )
    missing = tmp_path / "project_rules" / "missing.yaml"
    server = serve(project, missing, global_indexes=[user])
    # 実行
    result = server.call("list_rules", project_dir=str(e2e_project), format="json")
    # 検証
    content = result.structured_content
    assert content["unreadable_indexes"][0]["index"] == str(missing)
    assert content["unreadable_indexes"][0]["reason"]
    assert "RULE_INJECT_E2E_UNSET_NAME" in content["skipped_entries"][0]["reason"]
    assert content["disabled_entries"][0]["rule"] == str(off_rule)
    assert str(off_rule) not in [entry["rule"] for entry in content["entries"]]


def test_error_when_project_dir_not_absolute(
    tmp_path: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
    tool_text: Callable[[CallToolResult], str],
) -> None:
    """プロジェクトの直下に相対パスを渡すと、絶対パスで渡す旨のエラーを受け取る（異常シナリオ）。"""
    # 準備
    user, project, _, _ = _indexes(tmp_path, make_text_file, make_rule)
    server = serve(project, global_indexes=[user])
    # 実行
    result = server.call("list_rules", project_dir="project", format="json")
    # 検証
    assert result.is_error is True
    assert "絶対パス" in tool_text(result)
