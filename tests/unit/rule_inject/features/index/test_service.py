"""features/index/service.py の単体テスト。"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.index import (
    load_indexes,
    match_path,
    match_read_by,
    match_tool,
    rule_locations,
)
from rule_inject.features.index.service import (
    _argument_values,
    _compile_pattern,
    _glob_match,
    _match_args,
    _match_pattern,
)
from rule_inject.features.index.types import MatchedRule, MatchPattern


def test_load_indexes(
    tmp_path: Path,
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """渡された索引を順に読む（正常系）。"""
    # 準備
    first = make_index(index_text("./u.md"), "first/index.yaml")
    second = make_index(index_text("../r/p.md"), "second/idx.yaml")
    third = make_index(index_text("/rules/abs.md"), "third.yaml")
    # 実行
    result = load_indexes([str(first), str(second), str(third)], {})
    # 検証
    assert [entry.location for entry in result.entries] == [
        str(tmp_path / "first" / "u.md"),
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
    # 実行
    result = load_indexes([str(with_default), str(without_default)], {})
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
    # 実行
    result = load_indexes([str(missing), str(broken), str(valid)], {})
    # 検証
    assert {failure.path for failure in result.failures} == {str(missing), str(broken)}
    assert [entry.location for entry in result.entries] == ["/r/ok.md"]


def test_load_indexes_when_rule_has_variable(
    tmp_path: Path,
    make_index: Callable[..., Path],
) -> None:
    """`rule` の変数参照を展開してから解く（正常系）。"""
    # 準備
    index = make_index('rules:\n  - rule: "!{RULES}/a.md"\n  - rule: "./!{SUB}/b.md"\n')
    env = {"RULES": "/r", "SUB": "s"}
    # 実行
    result = load_indexes([str(index)], env)
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/a.md", str(tmp_path / "s" / "b.md")]
    assert not result.failures


def test_load_indexes_when_rule_variable_unset(
    make_index: Callable[..., Path],
) -> None:
    """展開できないエントリだけを読み飛ばす（正常系）。"""
    # 準備
    index = make_index('rules:\n  - rule: "!{UNSET}/a.md"\n  - rule: /r/ok.md\n')
    # 実行
    result = load_indexes([str(index)], {})
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/ok.md"]
    assert len(result.failures) == 1
    assert result.failures[0].path == str(index)
    assert "!{UNSET}/a.md" in result.failures[0].reason
    assert "UNSET" in result.failures[0].reason


def test_load_indexes_when_regex_unreadable(
    make_index: Callable[..., Path],
) -> None:
    """読めない正規表現を持つエントリだけを読み飛ばす（正常系）。"""
    # 準備
    index = make_index(
        "rules:\n"
        "  - rule: /r/bad.md\n"
        "    paths:\n"
        '      - "re:["\n'
        "  - rule: /r/ok.md\n"
        "    paths:\n"
        "      - 're:\\.py$'\n"
        "    args:\n"
        "      kind:\n"
        "        - rule\n"
    )
    # 実行
    result = load_indexes([str(index)], {})
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/ok.md"]
    assert result.entries[0].paths[0].regex.pattern == "\\.py$"
    assert result.entries[0].args[0].key == "kind"
    assert result.entries[0].args[0].patterns[0].source == "rule"
    assert len(result.failures) == 1
    assert result.failures[0].path == str(index)
    assert "re:[" in result.failures[0].reason


def test_load_indexes_when_read_by(
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """`read_by` を `ReadByCondition` にして読む（正常系）。"""
    # 準備
    with_read_by = make_index(
        index_text(
            "/r/a.md",
            read_by=[{"tools": ["re:__get_doc$"], "args": {"path": ["*.md"]}}],
        ),
        "a.yaml",
    )
    without_read_by = make_index(index_text("/r/b.md"), "b.yaml")
    # 実行
    result = load_indexes([str(with_read_by), str(without_read_by)], {})
    # 検証
    assert len(result.entries[0].read_by) == 1
    condition = result.entries[0].read_by[0]
    assert condition.tools[0].regex.pattern == "__get_doc$"
    assert len(condition.args) == 1
    assert condition.args[0].key == "path"
    assert condition.args[0].patterns[0].source == "*.md"
    assert result.entries[1].read_by == ()
    assert not result.failures


def test_load_indexes_when_rule_is_url(
    make_index: Callable[..., Path],
) -> None:
    """`rule` が URL のエントリだけを読み飛ばす（正常系）。"""
    # 準備
    index = make_index(
        'rules:\n  - rule: https://example.com/a.md\n  - rule: "!{BASE}/b.md"\n  - rule: /r/ok.md\n'
    )
    env = {"BASE": "http://example.com"}
    # 実行
    result = load_indexes([str(index)], env)
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/ok.md"]
    assert len(result.failures) == 2
    assert all(failure.path == str(index) for failure in result.failures)
    assert "https://example.com/a.md" in result.failures[0].reason
    assert "http://example.com/b.md" in result.failures[1].reason


def test_load_indexes_when_empty() -> None:
    """索引が無ければ何も読まない（正常系）。"""
    # 実行
    result = load_indexes([], {})
    # 検証
    assert not result.entries
    assert not result.failures


def test_load_indexes_when_entry_disabled(
    make_index: Callable[..., Path],
) -> None:
    """`enabled: false` のエントリを外す（正常系）。"""
    # 準備
    index = make_index(
        "rules:\n"
        "  - rule: /r/off.md\n"
        "    enabled: false\n"
        '  - rule: "!{UNSET}/a.md"\n'
        "    enabled: false\n"
        "  - rule: /r/on.md\n"
        "    enabled: true\n"
        "  - rule: /r/default.md\n"
    )
    # 実行
    result = load_indexes([str(index)], {})
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/on.md", "/r/default.md"]
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


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(
            "/p/src/app.py",
            [MatchedRule(location="/r/py.md", blocking=True)],
            id="matched",
        ),
        pytest.param("/p/src/_gen.py", [], id="excluded"),
    ],
)
def test_match_path_when_regex(
    make_entry: Callable[..., Any],
    path: str,
    expected: list[MatchedRule],
) -> None:
    """`re:` のパターンに部分一致で当て、正規表現の `exclude` で外す（正常系）。"""
    # 準備
    entries = [
        make_entry(
            "/r/py.md",
            paths=["re:/src/[a-z_]+\\.py$"],
            exclude=["re:/src/_"],
            on=["write"],
        ),
    ]
    # 実行
    result = match_path(entries, path, "write")
    # 検証
    assert result == expected


def test_match_tool(make_entry: Callable[..., Any]) -> None:
    """ツール名の glob に当てる（正常系）。"""
    # 準備
    entries = [make_entry("/r/create.md", tools=["mcp__*__create_*"])]
    # 実行
    result = match_tool(entries, "mcp__github__create_issue", {})
    # 検証
    assert result == [MatchedRule(location="/r/create.md", blocking=True)]


def test_match_tool_when_not_matched(make_entry: Callable[..., Any]) -> None:
    """当たらないツール名は空を返す（正常系）。"""
    # 準備
    entries = [make_entry("/r/create.md", tools=["mcp__*__create_*"])]
    # 実行
    result = match_tool(entries, "mcp__github__list_issues", {})
    # 検証
    assert result == []


def test_match_tool_when_args_match(make_entry: Callable[..., Any]) -> None:
    """引数の条件が全て当たれば当てる（正常系）。"""
    # 準備
    entries = [
        make_entry(
            "/r/search.md",
            tools=["mcp__*__search_*"],
            args={"tags": ["re:^python$"], "filter.kind": ["rule"]},
        ),
    ]
    tool_input = {"tags": ["go", "python"], "filter": {"kind": "rule"}}
    # 実行
    result = match_tool(entries, "mcp__docs__search_docs", tool_input)
    # 検証
    assert result == [MatchedRule(location="/r/search.md", blocking=True)]


def test_match_tool_when_args_partly_unmatched(make_entry: Callable[..., Any]) -> None:
    """引数の条件が 1 つでも当たらなければ当てない（正常系）。"""
    # 準備
    entries = [
        make_entry(
            "/r/search.md",
            tools=["mcp__*__search_*"],
            args={"tags": ["re:^python$"], "filter.kind": ["rule"]},
        ),
    ]
    # 実行
    result = match_tool(entries, "mcp__docs__search_docs", {"tags": ["python"]})
    # 検証
    assert result == []


def test_match_tool_when_regex_tool(make_entry: Callable[..., Any]) -> None:
    """ツール名の正規表現に部分一致で当てる（正常系）。"""
    # 準備
    entries = [make_entry("/r/create.md", tools=["re:__create_"])]
    # 実行
    result = match_tool(entries, "mcp__github__create_issue", {})
    # 検証
    assert result == [MatchedRule(location="/r/create.md", blocking=True)]


def test_match_read_by(make_entry: Callable[..., Any]) -> None:
    """`read_by` のツール名と引数に当てる（正常系）。"""
    # 準備
    entries = [
        make_entry(
            "/r/doc.md",
            read_by=[{"tools": ["mcp__docs__get_doc"], "args": {"path": ["re:\\.md$"]}}],
        ),
    ]
    # 実行
    result = match_read_by(entries, "mcp__docs__get_doc", {"path": "a.md"})
    # 検証
    assert result == ["/r/doc.md"]


def test_match_read_by_when_args_unmatched(make_entry: Callable[..., Any]) -> None:
    """引数が当たらなければ当てない（正常系）。"""
    # 準備
    entries = [
        make_entry(
            "/r/doc.md",
            read_by=[{"tools": ["mcp__docs__get_doc"], "args": {"path": ["re:\\.md$"]}}],
        ),
    ]
    # 実行
    result = match_read_by(entries, "mcp__docs__get_doc", {"path": "a.txt"})
    # 検証
    assert result == []


def test_match_read_by_when_any_condition(make_entry: Callable[..., Any]) -> None:
    """要素のどれか 1 つに当たれば当てる（正常系）。"""
    # 準備
    entries = [
        make_entry(
            "/r/doc.md",
            read_by=[{"tools": ["mcp__a__x"]}, {"tools": ["mcp__b__*"]}],
        ),
    ]
    # 実行
    result = match_read_by(entries, "mcp__b__get", {})
    # 検証
    assert result == ["/r/doc.md"]


def test_match_read_by_when_guide_only(make_entry: Callable[..., Any]) -> None:
    """案内の `tools` に当たるだけでは当てない（正常系）。"""
    # 準備
    entries = [make_entry("/r/doc.md", tools=["mcp__*"])]
    # 実行
    result = match_read_by(entries, "mcp__docs__get_doc", {})
    # 検証
    assert result == []


def test_match_read_by_when_duplicate(make_entry: Callable[..., Any]) -> None:
    """同じルールのエントリを 1 件にまとめる（正常系）。"""
    # 準備
    read_by = [{"tools": ["mcp__docs__get_doc"]}]
    entries = [
        make_entry("/r/doc.md", read_by=read_by),
        make_entry("/r/doc.md", read_by=read_by),
    ]
    # 実行
    result = match_read_by(entries, "mcp__docs__get_doc", {})
    # 検証
    assert result == ["/r/doc.md"]


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


def test_compile_pattern_when_regex() -> None:
    """`re:` で始まるパターンをコンパイルする（正常系）。"""
    # 実行
    result = _compile_pattern("re:^a.+b$")
    # 検証
    assert result.source == "re:^a.+b$"
    assert result.regex.pattern == "^a.+b$"


def test_compile_pattern_when_glob() -> None:
    """`re:` で始まらないパターンは glob のままにする（正常系）。"""
    # 実行
    result = _compile_pattern("**/*.py")
    # 検証
    assert result.source == "**/*.py"
    assert result.regex is None


def test_compile_pattern_when_invalid_regex() -> None:
    """読めない正規表現を拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(re.error, match="unterminated character set"):
        _compile_pattern("re:[")


def test_match_pattern_when_regex_partial() -> None:
    """正規表現は部分一致で当たる（正常系）。"""
    # 準備
    pattern = MatchPattern(source="re:src/", regex=re.compile("src/"))
    # 実行
    result = _match_pattern(pattern, "/p/src/a.py", glob_match=_glob_match)
    # 検証
    assert result is True


def test_match_pattern_when_regex_anchored() -> None:
    """アンカーで全体一致にできる（正常系）。"""
    # 準備
    pattern = MatchPattern(source="re:^python$", regex=re.compile("^python$"))
    # 実行
    result = _match_pattern(pattern, "python3", glob_match=_glob_match)
    # 検証
    assert result is False


def test_argument_values_when_nested_array() -> None:
    """途中の配列を要素ごとにたどる（正常系）。"""
    # 準備
    tool_input = {"filters": [{"tag": "a"}, {"tag": "b"}, {"x": 1}]}
    # 実行
    result = _argument_values(tool_input, "filters.tag")
    # 検証
    assert result == ["a", "b"]


def test_argument_values_when_scalars() -> None:
    """文字列以外のスカラーを JSON の表記にする（正常系）。"""
    # 準備
    tool_input = {"v": [True, None, 1.5, "s", {"k": 1}]}
    # 実行
    result = _argument_values(tool_input, "v")
    # 検証
    assert result == ["true", "null", "1.5", "s"]


def test_argument_values_when_missing() -> None:
    """無いキーは空を返す（正常系）。"""
    # 実行
    result = _argument_values({"a": "x"}, "a.b")
    # 検証
    assert result == []


def test_match_args_when_empty() -> None:
    """条件が空なら当たる（正常系）。"""
    # 実行
    result = _match_args([], {})
    # 検証
    assert result is True
