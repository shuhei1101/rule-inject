"""インターフェース定義『エントリの削除』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolResult

UNREAD_REV = "000000000000"


def _two_entries(a: Path, b: Path) -> str:
    """コメントを持つエントリを 2 つ持つ索引の文字列。"""
    return (
        "rules:\n"
        "  # 1 つ目のルール\n"
        f"  - rule: {a}  # a の行末\n"
        '    paths: ["**/*.py"]\n'
        "  # 2 つ目のルール\n"
        f"  - rule: {b}\n"
        '    paths: ["**/*.ts"]\n'
    )


def test_normal(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
) -> None:
    """位置で指したエントリを削除し、他のエントリとコメントを残す（正常系）。"""
    # 準備
    a = make_index("# a\n", "rules/a.md")
    b = make_index("# b\n", "rules/b.md")
    index = make_index(_two_entries(a, b))
    server = running_server(index)
    expected_rev = list_revs(server)[0]
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=expected_rev,
    )
    # 検証
    assert index.read_text(encoding="utf-8") == (
        f'rules:\n  # 2 つ目のルール\n  - rule: {b}\n    paths: ["**/*.ts"]\n'
    )
    assert result.structured_content["rule"] == str(a)
    assert result.structured_content["written"] is True


def test_normal_when_dry_run(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
) -> None:
    """`dry_run` で差分だけを返す（正常系）。"""
    # 準備
    a = make_index("# a\n", "rules/a.md")
    b = make_index("# b\n", "rules/b.md")
    index = make_index(_two_entries(a, b))
    before = index.read_bytes()
    server = running_server(index)
    expected_rev = list_revs(server)[0]
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=expected_rev,
        dry_run=True,
    )
    # 検証
    assert result.structured_content["written"] is False
    assert str(a) in result.structured_content["diff"]
    assert index.read_bytes() == before


def test_normal_when_existing_problems_remain(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
) -> None:
    """他のエントリにもとから問題が残っていても削除する（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    remaining = f"  - rule: {rule}\n    paths: []\n"
    index = make_index(f"rules:\n  - rule: {tmp_path}/rules/missing.md\n{remaining}")
    server = running_server(index)
    expected_rev = list_revs(server)[0]
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=expected_rev,
    )
    # 検証
    assert result.structured_content["written"] is True
    assert index.read_text(encoding="utf-8") == f"rules:\n{remaining}"


def test_error_when_project_dir_not_absolute(
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """相対パスの `project_dir` をエラーにする（異常系）。"""
    # 準備
    index = make_index("rules: []\n")
    server = running_server(index)
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir="project",
        index=str(index),
        position=0,
        expected_rev=UNREAD_REV,
    )
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
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n")
    before = index.read_bytes()
    server = running_server(index)
    config = invalid_config()
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=UNREAD_REV,
    )
    # 検証
    assert result.is_error is True
    assert config in text_of(result)
    assert "foo" in text_of(result)
    assert index.read_bytes() == before


def test_error_when_not_configured_index(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """設定ファイルで読まないファイルからの削除を断る（異常系）。"""
    # 準備
    a = make_index("# a\n", "rules/a.md")
    b = make_index("# b\n", "rules/b.md")
    index = make_index(_two_entries(a, b))
    other = make_index(_two_entries(a, b), "other/rules.yaml")
    before = other.read_bytes()
    server = running_server(index)
    expected_rev = list_revs(server)[0]
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(other),
        position=0,
        expected_rev=expected_rev,
    )
    # 検証
    assert result.is_error is True
    assert "設定ファイルで読む索引でない" in text_of(result)
    assert other.read_bytes() == before


def test_error_when_index_unparsable(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """YAML として読めない索引からの削除を断る（異常系）。"""
    # 準備
    index = make_index("rules:\n  - rule: a.md\n    paths: [x\n")
    before = index.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=UNREAD_REV,
    )
    # 検証
    assert result.is_error is True
    assert str(index) in text_of(result)
    assert index.read_bytes() == before


def test_error_when_entry_not_found(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """エントリの数以上の位置の削除を断る（異常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n")
    before = index.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=1,
        expected_rev=UNREAD_REV,
    )
    # 検証
    assert result.is_error is True
    assert "位置 1" in text_of(result)
    assert "1 件" in text_of(result)
    assert index.read_bytes() == before


def test_error_when_rev_mismatch(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """一覧を取った後に書き換えられたエントリの削除を断る（異常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f'rules:\n  - rule: {rule}\n    paths: ["**/*.py"]\n')
    server = running_server(index)
    stale_rev = list_revs(server)[0]
    index.write_text(f'rules:\n  - rule: {rule}\n    paths: ["**/*.ts"]\n', encoding="utf-8")
    changed = index.read_bytes()
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=stale_rev,
    )
    # 検証
    assert result.is_error is True
    assert list_revs(server)[0] in text_of(result)
    assert "list_rules" in text_of(result)
    assert index.read_bytes() == changed


@pytest.mark.parametrize(
    ("text", "line"),
    [
        pytest.param("rules:\n  - rule: a.md\n    on: [foo]\n", "2行目", id="invalid_on"),
        pytest.param("rules: [{rule: a.md}, {rule: b.md}]\n", "1行目", id="flow_rules"),
    ],
)
def test_error_when_hook_unreadable(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
    text: str,
    line: str,
) -> None:
    """フックが読めない索引からの削除を断る（異常系）。"""
    # 準備
    index = make_index(text)
    before = index.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=UNREAD_REV,
    )
    # 検証
    assert result.is_error is True
    assert line in text_of(result)
    assert "手で直" in text_of(result)
    assert index.read_bytes() == before
