"""features/index/service.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.index import load_indexes, match_path, match_tool, rule_locations
from rule_inject.features.index.service import _glob_match
from rule_inject.features.index.types import MatchedRule


def test_load_indexes(
    tmp_path: Path,
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """ユーザーとプロジェクトの索引を合わせて読む（正常系）。"""
    # 準備
    user_index = make_index(index_text("./u.md"), "user/index.yaml")
    make_index(index_text("../r/p.md"), "proj/idx.yaml")
    absolute_index = make_index(index_text("/rules/abs.md"), "abs.yaml")
    env = {
        "RULE_INJECT_INDEXES_USER": str(user_index),
        "RULE_INJECT_INDEXES_PROJECT": f"proj/idx.yaml, {absolute_index}",
        "CLAUDE_PROJECT_DIR": str(tmp_path),
    }
    # 実行
    result = load_indexes(env)
    # 検証
    assert [entry.location for entry in result.entries] == [
        str(tmp_path / "user" / "u.md"),
        str(tmp_path / "r" / "p.md"),
        "/rules/abs.md",
    ]
    assert not result.failures


def test_load_indexes_when_on_missing(
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """`on` を `default_on` と `DEFAULT_ON` で埋める（正常系）。"""
    # 準備
    with_default = make_index(index_text("/r/a.md", default_on=["write"]), "a.yaml")
    without_default = make_index(index_text("/r/b.md"), "b.yaml")
    env = {"RULE_INJECT_INDEXES_PROJECT": f"{with_default},{without_default}"}
    # 実行
    result = load_indexes(env)
    # 検証
    assert result.entries[0].on == frozenset({"write"})
    assert result.entries[1].on == frozenset({"read", "write", "mcp"})


def test_load_indexes_when_unreadable(
    tmp_path: Path,
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """読めない索引を failures に集めて続ける（正常系）。"""
    # 準備
    missing = tmp_path / "missing.yaml"
    broken = make_index("rules:\n  - foo: bar\n", "broken.yaml")
    valid = make_index(index_text("/r/ok.md"), "valid.yaml")
    env = {"RULE_INJECT_INDEXES_PROJECT": f"{missing},{broken},{valid}"}
    # 実行
    result = load_indexes(env)
    # 検証
    assert {failure.path for failure in result.failures} == {str(missing), str(broken)}
    assert [entry.location for entry in result.entries] == ["/r/ok.md"]


def test_load_indexes_when_no_env() -> None:
    """環境変数が無ければ何も読まない（正常系）。"""
    # 実行
    result = load_indexes({})
    # 検証
    assert not result.entries
    assert not result.failures


def test_match_path(make_entry: Callable[..., Any]) -> None:
    """当たるエントリを選ぶ（正常系）。"""
    # 準備
    entries = [
        make_entry("/r/py.md", paths=["**/*.py"], on=["write"]),
        make_entry("/r/ts.md", paths=["**/*.ts"], on=["write"]),
    ]
    # 実行
    result = match_path(entries, "/p/src/a.py", "write")
    # 検証
    assert result == [MatchedRule(location="/r/py.md", blocking=True)]


def test_match_path_when_excluded(make_entry: Callable[..., Any]) -> None:
    """外すパスには当てない（正常系）。"""
    # 準備
    entries = [make_entry("/r/py.md", paths=["**/*.py"], exclude=["**/tests/**"])]
    # 実行
    result = match_path(entries, "/p/tests/a.py", "write")
    # 検証
    assert result == []


def test_match_path_when_duplicate(make_entry: Callable[..., Any]) -> None:
    """同じルールのエントリを 1 件にまとめる（正常系）。"""
    # 準備
    entries = [
        make_entry("/r/py.md", paths=["**/*.py"], on=["read"]),
        make_entry("/r/py.md", paths=["**/*.py"], on=["write"]),
    ]
    # 実行
    result = match_path(entries, "/p/src/a.py", "write")
    # 検証
    assert result == [MatchedRule(location="/r/py.md", blocking=True)]


def test_match_path_when_not_blocking(make_entry: Callable[..., Any]) -> None:
    """操作が `on` に無ければ止めない（正常系）。"""
    # 準備
    entries = [make_entry("/r/py.md", paths=["**/*.py"], on=["write"])]
    # 実行
    result = match_path(entries, "/p/src/a.py", "read")
    # 検証
    assert result == [MatchedRule(location="/r/py.md", blocking=False)]


def test_match_tool(make_entry: Callable[..., Any]) -> None:
    """ツール名の glob に当てる（正常系）。"""
    # 準備
    entries = [make_entry("/r/create.md", tools=["mcp__*__create_*"])]
    # 実行
    result = match_tool(entries, "mcp__github__create_issue")
    # 検証
    assert result == [MatchedRule(location="/r/create.md", blocking=True)]


def test_match_tool_when_not_matched(make_entry: Callable[..., Any]) -> None:
    """当たらないツール名は空を返す（正常系）。"""
    # 準備
    entries = [make_entry("/r/create.md", tools=["mcp__*__create_*"])]
    # 実行
    result = match_tool(entries, "mcp__github__list_issues")
    # 検証
    assert result == []


def test_rule_locations(make_entry: Callable[..., Any]) -> None:
    """重なりを落とした集合を返す（正常系）。"""
    # 準備
    entries = [
        make_entry("/r/a.md", paths=["**/*.py"]),
        make_entry("/r/a.md", tools=["mcp__*"]),
        make_entry("/r/b.md", paths=["**/*.ts"]),
    ]
    # 実行
    result = rule_locations(entries)
    # 検証
    assert result == frozenset({"/r/a.md", "/r/b.md"})


@pytest.mark.parametrize("path", ["/a/b/c.py", "/c.py"])
def test_glob_match_when_double_star(path: str) -> None:
    """`**` がフォルダをまたぐ（正常系）。"""
    # 実行
    result = _glob_match("**/*.py", path)
    # 検証
    assert result is True


def test_glob_match_when_single_star() -> None:
    """`*` はフォルダをまたがない（正常系）。"""
    # 実行
    result = _glob_match("*/x/*.md", "/a/x/b/c.md")
    # 検証
    assert result is False


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param("/a/b.tsx", True, id="matched"),
        pytest.param("/a/b.js", False, id="not_matched"),
    ],
)
def test_glob_match_when_braces(path: str, expected: bool) -> None:
    """波括弧の候補を選ぶ（正常系）。"""
    # 実行
    result = _glob_match("**/*.{ts,tsx}", path)
    # 検証
    assert result is expected
