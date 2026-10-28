"""インターフェース定義『ルールの一覧』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolResult


@pytest.fixture
def two_indexes(tmp_path: Path, make_index: Callable[..., Path]) -> tuple[Path, Path]:
    """ユーザーの索引とプロジェクトの索引（どちらも `on` を書かないエントリと `on: [write]` のエントリを 1 つずつ）。"""
    user = make_index(
        f"rules:\n  - rule: {tmp_path}/rules/u1.md\n  - rule: {tmp_path}/rules/u2.md\n    on: [write]\n",
        "user/rules.yaml",
    )
    project = make_index(
        f"rules:\n  - rule: {tmp_path}/rules/p1.md\n  - rule: {tmp_path}/rules/p2.md\n    on: [write]\n",
        "project/rules.yaml",
    )
    return user, project


def test_normal(
    tmp_path: Path,
    project_dir: Path,
    two_indexes: tuple[Path, Path],
    running_server: Callable[..., Any],
) -> None:
    """ユーザーの索引とプロジェクトの索引のエントリを、フックが読む順に返す（正常系）。"""
    # 準備
    user, project = two_indexes
    server = running_server(project, global_indexes=[user])
    # 実行
    result = server.call("list_rules", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    assert content["config_path"] == str(server.config_path)
    assert content["indexes"] == [str(user), str(project)]
    assert [entry["rule"] for entry in content["entries"]] == [
        f"{tmp_path}/rules/u1.md",
        f"{tmp_path}/rules/u2.md",
        f"{tmp_path}/rules/p1.md",
        f"{tmp_path}/rules/p2.md",
    ]
    assert content["entries"][0]["on"] == ["read", "write", "mcp"]
    assert content["entries"][1]["on"] == ["write"]
    assert content["total"] == 4
    assert content["next_cursor"] is None


def test_normal_when_some_entries_excluded(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    two_indexes: tuple[Path, Path],
    running_server: Callable[..., Any],
) -> None:
    """読めない索引・読み飛ばしたエントリ・無効のエントリを分けて返す（正常系）。"""
    # 準備
    user, _ = two_indexes
    project = make_index(
        f"rules:\n  - rule: {tmp_path}/rules/p1.md\n"
        '  - rule: "!{RULE_INJECT_TEST_UNSET_NAME}/a.md"\n'
        f"  - rule: {tmp_path}/rules/off.md\n    enabled: false\n",
        "project/rules.yaml",
    )
    missing = tmp_path / "project" / "missing.yaml"
    server = running_server(project, missing, global_indexes=[user])
    # 実行
    result = server.call("list_rules", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    assert content["unreadable_indexes"][0]["index"] == str(missing)
    assert content["unreadable_indexes"][0]["reason"]
    assert content["skipped_entries"][0]["position"] == 1
    assert "RULE_INJECT_TEST_UNSET_NAME" in content["skipped_entries"][0]["reason"]
    assert content["disabled_entries"][0]["position"] == 2
    assert content["disabled_entries"][0]["rule"] == f"{tmp_path}/rules/off.md"
    assert f"{tmp_path}/rules/off.md" not in [entry["rule"] for entry in content["entries"]]


def test_normal_when_paged(
    project_dir: Path,
    two_indexes: tuple[Path, Path],
    running_server: Callable[..., Any],
) -> None:
    """`limit` を超えた分を `next_cursor` で続けて取る（正常系）。"""
    # 準備
    user, project = two_indexes
    server = running_server(project, global_indexes=[user])
    # 実行
    first = server.call("list_rules", project_dir=str(project_dir), limit=3, format="json")
    second = server.call(
        "list_rules",
        project_dir=str(project_dir),
        limit=3,
        cursor=first.structured_content["next_cursor"],
        format="json",
    )
    # 検証
    assert len(first.structured_content["entries"]) == 3
    assert first.structured_content["next_cursor"] is not None
    assert len(second.structured_content["entries"]) == 1
    assert second.structured_content["next_cursor"] is None
    assert first.structured_content["total"] == 4
    assert second.structured_content["total"] == 4


def test_error_when_project_dir_not_absolute(
    two_indexes: tuple[Path, Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """相対パスの `project_dir` をエラーにする（異常系）。"""
    # 準備
    user, project = two_indexes
    server = running_server(project, global_indexes=[user])
    # 実行
    result = server.call("list_rules", project_dir="project", format="json")
    # 検証
    assert result.is_error is True
    assert "絶対パス" in text_of(result)


def test_error_when_settings_unreadable(
    project_dir: Path,
    two_indexes: tuple[Path, Path],
    running_server: Callable[..., Any],
    invalid_config: Callable[[], str],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """呼び出しの時点で読めない設定ファイルをエラーにする（異常系）。"""
    # 準備
    user, project = two_indexes
    server = running_server(project, global_indexes=[user])
    config = invalid_config()
    # 実行
    result = server.call("list_rules", project_dir=str(project_dir), format="json")
    # 検証
    assert result.is_error is True
    assert config in text_of(result)
    assert "foo" in text_of(result)
