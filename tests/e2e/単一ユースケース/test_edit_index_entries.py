"""単一ユースケース「索引のエントリを編集する」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

from rule_inject.features.index import load_indexes

LONG_GLOB = "**/" + "x" * 80 + "/*.py"
UNREAD_REV = "000000000000"


def _revs(server: Any, project_dir: Path) -> list[str]:
    """一覧のツールが返す効いているエントリのバージョンを、位置の順に返す。"""
    result = server.call("list_rules", project_dir=str(project_dir), format="json")
    return [entry["rev"] for entry in result.structured_content["entries"]]


def _two_entries(first: Path, second: Path) -> str:
    """コメントを持つエントリを 2 つ持つ索引の文字列。"""
    return (
        "rules:\n"
        "  # 1 つ目のルール\n"
        f"  - rule: {first}\n"
        '    paths: ["**/*.py"]\n'
        "  # 2 つ目のルール\n"
        f"  - rule: {second}\n"
        '    paths: ["**/*.ts"]\n'
    )


def test_normal_when_entry_created(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """末尾にエントリが追加され、他の行は変わらず、フックと同じ読み取りで読める（正常シナリオ）。"""
    # 準備
    # 索引の `rule: 'python.md'` は、索引と同じ rules フォルダのファイルを指す
    make_rule("python.md", "# python\n")
    new_rule = make_rule("new.md", "# new\n")
    before = (
        "# ルールの索引\n"
        "default_on: [write]  # 既定\n"
        "rules:\n"
        "  # python のルール\n"
        "  - rule: 'python.md'\n"
        '    paths: ["**/*.py"]\n'
    )
    index = make_text_file("rules/index.yaml", before)
    server = serve(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(e2e_project),
        index=str(index),
        entry={"rule": str(new_rule), "paths": [LONG_GLOB], "on": ["write"]},
    )
    # 検証
    after = index.read_text(encoding="utf-8")
    appended = after[len(before) :].splitlines()
    loaded = load_indexes([str(index)], {})
    assert after.startswith(before)
    assert len(appended) == 3
    assert appended[1].startswith("    paths: [")
    assert appended[1].endswith("]")
    assert LONG_GLOB in appended[1]
    assert loaded.entries[-1].location == str(new_rule)
    assert loaded.failures == ()
    assert result.structured_content["position"] == 1


def test_normal_when_entry_updated(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """2 つ目のエントリの `paths` だけが書き換わり、1 つ目とコメントは変わらない（正常シナリオ）。"""
    # 準備
    first = make_rule("a.md", "# a\n")
    second = make_rule("b.md", "# b\n")
    before = _two_entries(first, second)
    index = make_text_file("rules.yaml", before)
    server = serve(index)
    expected_rev = _revs(server, e2e_project)[1]
    # 実行
    server.call(
        "write_index_entry",
        project_dir=str(e2e_project),
        index=str(index),
        position=1,
        expected_rev=expected_rev,
        entry={"paths": ["**/*.tsx"]},
    )
    # 検証
    before_lines = before.splitlines()
    after_lines = index.read_text(encoding="utf-8").splitlines()
    assert [line for line in before_lines if line not in after_lines] == ['    paths: ["**/*.ts"]']
    assert [line for line in after_lines if line not in before_lines] == ["    paths: ['**/*.tsx']"]
    assert "  # 1 つ目のルール" in after_lines
    assert f"  - rule: {first}" in after_lines


def test_normal_when_entry_disabled(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """`enabled: false` が書かれ、フックと同じ読み取りで照合に使われない（正常シナリオ）。"""
    # 準備
    rule = make_rule("a.md", "# a\n")
    index = make_text_file("rules.yaml", f'rules:\n  - rule: {rule}\n    paths: ["**/*.py"]\n')
    server = serve(index)
    expected_rev = _revs(server, e2e_project)[0]
    # 実行
    server.call(
        "write_index_entry",
        project_dir=str(e2e_project),
        index=str(index),
        position=0,
        expected_rev=expected_rev,
        entry={"enabled": False},
    )
    # 検証
    loaded = load_indexes([str(index)], {})
    assert "    enabled: false" in index.read_text(encoding="utf-8").splitlines()
    assert loaded.entries == ()
    assert loaded.failures == ()


def test_normal_when_entry_deleted(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """1 つ目のエントリが無くなり、2 つ目とそのコメントは変わらない（正常シナリオ）。"""
    # 準備
    first = make_rule("a.md", "# a\n")
    second = make_rule("b.md", "# b\n")
    index = make_text_file("rules.yaml", _two_entries(first, second))
    server = serve(index)
    expected_rev = _revs(server, e2e_project)[0]
    # 実行
    result = server.call(
        "delete_index_entry",
        project_dir=str(e2e_project),
        index=str(index),
        position=0,
        expected_rev=expected_rev,
    )
    # 検証
    assert index.read_text(encoding="utf-8") == (
        f'rules:\n  # 2 つ目のルール\n  - rule: {second}\n    paths: ["**/*.ts"]\n'
    )
    assert result.structured_content["rule"] == str(first)


def test_error_when_check_failed(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
    tool_text: Callable[[CallToolResult], str],
) -> None:
    """Schema に違反するエントリは、違反の場所と理由を返して書き込まない（異常シナリオ）。"""
    # 準備
    rule = make_rule("a.md", "# a\n")
    index = make_text_file("rules.yaml", f"rules:\n  - rule: {rule}\n")
    before = index.read_bytes()
    server = serve(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(e2e_project),
        index=str(index),
        entry={"rule": str(rule), "paths": []},
    )
    # 検証
    assert result.is_error is True
    assert "rules[1].paths" in tool_text(result)
    assert index.read_bytes() == before


def test_error_when_not_configured_index(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
    tool_text: Callable[[CallToolResult], str],
) -> None:
    """設定ファイルで読まないファイルへは、読む索引でない旨を返して書き込まない（異常シナリオ）。"""
    # 準備
    rule = make_rule("a.md", "# a\n")
    index = make_text_file("rules.yaml", f"rules:\n  - rule: {rule}\n")
    other = make_text_file("other/rules.yaml", f"rules:\n  - rule: {rule}\n")
    before = other.read_bytes()
    server = serve(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(e2e_project),
        index=str(other),
        entry={"rule": str(rule)},
    )
    # 検証
    assert result.is_error is True
    assert "設定ファイルで読む索引でない" in tool_text(result)
    assert other.read_bytes() == before


def test_error_when_entry_not_found(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
    tool_text: Callable[[CallToolResult], str],
) -> None:
    """エントリの数以上の位置は、位置が無い旨とエントリの数を返して書き込まない（異常シナリオ）。"""
    # 準備
    rule = make_rule("a.md", "# a\n")
    index = make_text_file("rules.yaml", f"rules:\n  - rule: {rule}\n")
    before = index.read_bytes()
    server = serve(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(e2e_project),
        index=str(index),
        position=1,
        expected_rev=UNREAD_REV,
        entry={"on": ["write"]},
    )
    # 検証
    assert result.is_error is True
    assert "位置 1" in tool_text(result)
    assert "1 件" in tool_text(result)
    assert index.read_bytes() == before
