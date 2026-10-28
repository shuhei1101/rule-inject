"""インターフェース定義『エントリの書き込み』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

from rule_inject.features.index import load_indexes

LONG_GLOB = "**/" + "x" * 80 + "/*.py"
UNREAD_REV = "000000000000"


def _two_entries(a: Path, b: Path) -> str:
    """コメントを持つエントリを 2 つ持つ索引の文字列。"""
    return (
        "rules:\n"
        "  # python のルール\n"
        f"  - rule: {a}\n"
        '    paths: ["**/*.py"]\n'
        "  # ts のルール\n"
        f"  - rule: {b}\n"
        '    paths: ["**/*.ts"]\n'
    )


def test_normal_when_entry_created(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """末尾にエントリを追加し、他の行を変えない（正常系）。"""
    # 準備
    existing = make_index("# python\n", "python.md")
    new_rule = make_index("# new\n", "rules/new.md")
    before = (
        "# ルールの索引\n"
        "default_on: [write]  # 既定\n"
        "rules:\n"
        "  # python のルール\n"
        "  - rule: 'python.md'\n"
        '    paths: ["**/*.py"]\n'
    )
    index = make_index(before)
    server = running_server(index)
    assert existing.exists()
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
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
    assert result.structured_content["written"] is True


def test_normal_when_entry_updated(
    make_index: Callable[..., Path],
    project_dir: Path,
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
) -> None:
    """位置で指したエントリのキーだけを書き換える（正常系）。"""
    # 準備
    a = make_index("# a\n", "rules/a.md")
    b = make_index("# b\n", "rules/b.md")
    before = _two_entries(a, b)
    index = make_index(before)
    server = running_server(index)
    expected_rev = list_revs(server)[1]
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=1,
        expected_rev=expected_rev,
        entry={"paths": ["**/*.tsx"]},
    )
    # 検証
    before_lines = before.splitlines()
    after_lines = index.read_text(encoding="utf-8").splitlines()
    removed = [line for line in before_lines if line not in after_lines]
    added = [line for line in after_lines if line not in before_lines]
    assert removed == ['    paths: ["**/*.ts"]']
    assert added == ["    paths: ['**/*.tsx']"]
    assert "  # python のルール" in after_lines
    assert "  # ts のルール" in after_lines
    assert result.structured_content["rev"] != expected_rev


def test_normal_when_entry_disabled(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
) -> None:
    """`enabled: false` を書き、照合に使われなくする（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f'rules:\n  - rule: {rule}\n    paths: ["**/*.py"]\n')
    server = running_server(index)
    expected_rev = list_revs(server)[0]
    # 実行
    server.call(
        "write_index_entry",
        project_dir=str(project_dir),
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


def test_normal_when_dry_run(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """`dry_run` でチェックと差分だけを返す（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    new_rule = make_index("# new\n", "rules/new.md")
    index = make_index(f"rules:\n  - rule: {rule}\n")
    before = index.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        entry={"rule": str(new_rule), "paths": [LONG_GLOB]},
        dry_run=True,
    )
    # 検証
    assert result.structured_content["written"] is False
    assert str(new_rule) in result.structured_content["diff"]
    assert index.read_bytes() == before


def test_normal_when_existing_problems_remain(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
) -> None:
    """他のエントリにもとから問題が残っていても、新しい問題を生まない書き込みは通す（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    second = f"  - rule: {tmp_path}/rules/missing.md\n"
    index = make_index(f"rules:\n  - rule: {rule}\n    paths: []\n{second}")
    server = running_server(index)
    expected_rev = list_revs(server)[0]
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=expected_rev,
        entry={"paths": ["**/*.py"]},
    )
    # 検証
    after = index.read_text(encoding="utf-8")
    assert result.structured_content["written"] is True
    assert "    paths: ['**/*.py']" in after.splitlines()
    assert after.endswith(second)


def test_error_when_arguments_invalid(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """`position` だけを渡し `expected_rev` を渡さない呼び出しをエラーにする（異常系）。"""
    # 準備
    index = make_index("rules: []\n")
    server = running_server(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        entry={"on": ["write"]},
    )
    # 検証
    assert result.is_error is True
    assert "expected_rev" in text_of(result)


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
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        entry={"rule": str(rule)},
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
    text_of: Callable[[CallToolResult], str],
) -> None:
    """設定ファイルで読まないファイルへの書き込みを断る（異常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n")
    other = make_index(f"rules:\n  - rule: {rule}\n", "other/rules.yaml")
    before = other.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(other),
        entry={"rule": str(rule)},
    )
    # 検証
    assert result.is_error is True
    assert "設定ファイルで読む索引でない" in text_of(result)
    assert str(index) in text_of(result)
    assert other.read_bytes() == before


def test_error_when_index_unparsable(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """YAML として読めない索引への書き込みを断る（異常系）。"""
    # 準備
    index = make_index("rules:\n  - rule: a.md\n    paths: [x\n")
    before = index.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        entry={"rule": "b.md"},
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
    """エントリの数以上の位置への書き込みを断る（異常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n")
    before = index.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=1,
        expected_rev=UNREAD_REV,
        entry={"on": ["write"]},
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
    """一覧を取った後に書き換えられたエントリへの書き込みを断る（異常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f'rules:\n  - rule: {rule}\n    paths: ["**/*.py"]\n')
    server = running_server(index)
    stale_rev = list_revs(server)[0]
    index.write_text(f'rules:\n  - rule: {rule}\n    paths: ["**/*.ts"]\n', encoding="utf-8")
    changed = index.read_bytes()
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=stale_rev,
        entry={"on": ["write"]},
    )
    # 検証
    assert result.is_error is True
    assert list_revs(server)[0] in text_of(result)
    assert "list_rules" in text_of(result)
    assert index.read_bytes() == changed


def test_error_when_check_failed(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """Schema に違反するエントリの新規作成を断る（異常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n")
    before = index.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        entry={"rule": str(rule), "paths": []},
    )
    # 検証
    assert result.is_error is True
    assert "rules[1].paths" in text_of(result)
    assert index.read_bytes() == before


def test_error_when_hook_unreadable(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """フックが読めない索引のエントリの書き換えを断る（異常系）。"""
    # 準備
    index = make_index("rules:\n  - rule: a.md\n    on: [foo]\n")
    before = index.read_bytes()
    server = running_server(index)
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=UNREAD_REV,
        entry={"on": ["write"]},
    )
    # 検証
    assert result.is_error is True
    assert "2行目" in text_of(result)
    assert "手で直" in text_of(result)
    assert index.read_bytes() == before


def test_error_when_layout_not_kept(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """対象のエントリの外の行が変わる書き込みを断る（異常系）。"""
    # 準備
    a = make_index("# a\n", "rules/a.md")
    b = make_index("# b\n", "rules/b.md")
    index = make_index(
        f"rules:\n  - rule: {a}\n    paths: [x]\n  - rule: {b}\n    paths: [docs/**, ~]\n"
    )
    before = index.read_bytes()
    server = running_server(index)
    expected_rev = list_revs(server)[0]
    # 実行
    result = server.call(
        "write_index_entry",
        project_dir=str(project_dir),
        index=str(index),
        position=0,
        expected_rev=expected_rev,
        entry={"on": ["write"]},
    )
    # 検証
    assert result.is_error is True
    assert "書式を保って書けない" in text_of(result)
    assert "5行目" in text_of(result)
    assert "手で直" in text_of(result)
    assert index.read_bytes() == before
