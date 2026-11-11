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
    match_read_tool,
    match_tool,
    merge_matched,
    rule_locations,
)
from rule_inject.features.index.service import (
    _argument_values,
    _compile_pattern,
    _glob_match,
    _json_equal,
    _match_args,
    _match_pattern,
)
from rule_inject.features.index.types import MatchedRule, MatchPattern, ReadTool
from rule_inject.shared.errors import IndexReadError


def test_load_indexes(
    tmp_path: Path,
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """引き渡された索引を順に読む（正常系）。"""
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
    regex = result.entries[0].paths[0].regex
    assert regex is not None
    assert regex.pattern == "\\.py$"
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
    tool_regex = condition.tools[0].regex
    assert tool_regex is not None
    assert tool_regex.pattern == "__get_doc$"
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
    """`enabled: false` のエントリを除外する（正常系）。"""
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
    """該当するエントリを選ぶ（正常系）。"""
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
    """除外するパスには照合しない（正常系）。"""
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
    """`re:` のパターンに部分一致で照合し、正規表現の `exclude` で除外する（正常系）。"""
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


def test_match_path_when_read_tool(make_entry: Callable[..., Any]) -> None:
    """該当したエントリの `read_tool` を記載する（正常系）。"""
    # 準備
    tool_a = ReadTool(tool="mcp__a__get", args={"id": "a"}, optional_args={})
    tool_a_again = ReadTool(tool="mcp__a__get", args={"id": "a"}, optional_args={})
    tool_b = ReadTool(tool="mcp__b__get", args={}, optional_args={})
    entries = [
        make_entry("/r/doc.md", paths=["**/*.py"], read_tool=tool_a),
        make_entry("/r/doc.md", paths=["**/*.py"]),
        make_entry("/r/doc.md", paths=["**/*.py"], read_tool=tool_a_again),
        make_entry("/r/doc.md", paths=["**/*.py"], read_tool=tool_b),
    ]
    # 実行
    result = match_path(entries, "/p/a.py", "write")
    # 検証
    assert result == [MatchedRule(location="/r/doc.md", blocking=True, read_tools=(tool_a, tool_b))]


def test_merge_matched() -> None:
    """場所ごとにまとめ、止めるかと参照するツールを合わせる（正常系）。"""
    # 準備
    tool_a = ReadTool(tool="mcp__a__get", args={}, optional_args={})
    tool_b = ReadTool(tool="mcp__b__get", args={}, optional_args={})
    rules = [
        MatchedRule(location="/r/a.md", blocking=False, read_tools=(tool_a,)),
        MatchedRule(location="/r/b.md", blocking=False),
        MatchedRule(location="/r/a.md", blocking=True, read_tools=(tool_a, tool_b)),
    ]
    # 実行
    result = merge_matched(rules)
    # 検証
    assert result == [
        MatchedRule(location="/r/a.md", blocking=True, read_tools=(tool_a, tool_b)),
        MatchedRule(location="/r/b.md", blocking=False),
    ]


def test_match_tool(make_entry: Callable[..., Any]) -> None:
    """ツール名の glob に照合する（正常系）。"""
    # 準備
    entries = [make_entry("/r/create.md", tools=["mcp__*__create_*"])]
    # 実行
    result = match_tool(entries, "mcp__github__create_issue", {})
    # 検証
    assert result == [MatchedRule(location="/r/create.md", blocking=True)]


def test_match_tool_when_not_matched(make_entry: Callable[..., Any]) -> None:
    """該当しないツール名は空を返却する（正常系）。"""
    # 準備
    entries = [make_entry("/r/create.md", tools=["mcp__*__create_*"])]
    # 実行
    result = match_tool(entries, "mcp__github__list_issues", {})
    # 検証
    assert result == []


def test_match_tool_when_args_match(make_entry: Callable[..., Any]) -> None:
    """引数の条件が全て該当すれば照合する（正常系）。"""
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
    """引数の条件が 1 つでも該当しなければ照合しない（正常系）。"""
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
    """ツール名の正規表現に部分一致で照合する（正常系）。"""
    # 準備
    entries = [make_entry("/r/create.md", tools=["re:__create_"])]
    # 実行
    result = match_tool(entries, "mcp__github__create_issue", {})
    # 検証
    assert result == [MatchedRule(location="/r/create.md", blocking=True)]


def test_match_read_by(make_entry: Callable[..., Any]) -> None:
    """`read_by` のツール名と引数に照合する（正常系）。"""
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
    """引数が該当しなければ照合しない（正常系）。"""
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
    """要素のどれか 1 つに該当すれば照合する（正常系）。"""
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
    """案内の `tools` に該当するだけでは照合しない（正常系）。"""
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


SEARCH_ARGS = {"filter": {"field": "id", "op": "eq", "values": ["python"]}, "sections": ["命名"]}


def test_match_read_tool(make_entry: Callable[..., Any]) -> None:
    """ツール名と引数が一致する呼び出しに照合する（正常系）。"""
    # 準備
    read_tool = ReadTool(tool="mcp__docs__search_docs", args=SEARCH_ARGS, optional_args={})
    entries = [make_entry("/r/doc.md", read_tool=read_tool)]
    tool_input = {
        "view": "full",
        "sections": ["命名"],
        "filter": {"values": ["python"], "op": "eq", "field": "id"},
    }
    # 実行
    result = match_read_tool(entries, "mcp__docs__search_docs", tool_input)
    # 検証
    assert result == ["/r/doc.md"]


@pytest.mark.parametrize(
    "tool_input",
    [
        pytest.param(
            {"filter": {"field": "id", "op": "eq", "values": ["python"]}, "sections": ["例外"]},
            id="sections_differ",
        ),
        pytest.param(
            {"filter": {"field": "id", "op": "eq", "values": ["python"]}}, id="sections_missing"
        ),
        pytest.param(
            {
                "filter": {"field": "id", "op": "eq", "values": ["python"]},
                "sections": ["命名", "例外"],
            },
            id="sections_longer",
        ),
        pytest.param(
            {"filter": {"field": "id", "op": "eq", "values": ["go"]}, "sections": ["命名"]},
            id="filter_values_differ",
        ),
    ],
)
def test_match_read_tool_when_args_unmatched(
    make_entry: Callable[..., Any], tool_input: dict[str, Any]
) -> None:
    """引数の値が違うか無ければ照合しない（正常系）。"""
    # 準備
    read_tool = ReadTool(tool="mcp__docs__search_docs", args=SEARCH_ARGS, optional_args={})
    entries = [make_entry("/r/doc.md", read_tool=read_tool)]
    # 実行
    result = match_read_tool(entries, "mcp__docs__search_docs", tool_input)
    # 検証
    assert result == []


def test_match_read_tool_when_tool_unmatched(make_entry: Callable[..., Any]) -> None:
    """ツール名が違えば照合しない（パターンとして読まない）（正常系）。"""
    # 準備
    read_tool = ReadTool(tool="mcp__docs__search_*", args={}, optional_args={})
    entries = [make_entry("/r/doc.md", read_tool=read_tool)]
    # 実行
    result = match_read_tool(entries, "mcp__docs__search_docs", {})
    # 検証
    assert result == []


@pytest.mark.parametrize(
    ("tool_input", "expected"),
    [
        pytest.param({"limit": 1, "full": True}, ["/r/doc.md"], id="same_types"),
        pytest.param({"limit": True, "full": True}, [], id="bool_for_number"),
        pytest.param({"limit": "1", "full": True}, [], id="string_for_number"),
    ],
)
def test_match_read_tool_when_scalar_not_string(
    make_entry: Callable[..., Any], tool_input: dict[str, Any], expected: list[str]
) -> None:
    """真偽値と数値・文字列を区別する（正常系）。"""
    # 準備
    read_tool = ReadTool(
        tool="mcp__docs__search_docs", args={"limit": 1, "full": True}, optional_args={}
    )
    entries = [make_entry("/r/doc.md", read_tool=read_tool)]
    # 実行
    result = match_read_tool(entries, "mcp__docs__search_docs", tool_input)
    # 検証
    assert result == expected


def test_match_read_tool_when_without_args(make_entry: Callable[..., Any]) -> None:
    """`args` の無い `read_tool` はツール名だけで照合する（正常系）。"""
    # 準備
    read_tool = ReadTool(tool="mcp__docs__search_docs", args={}, optional_args={})
    entries = [make_entry("/r/doc.md", read_tool=read_tool)]
    # 実行
    result = match_read_tool(entries, "mcp__docs__search_docs", {"id": "x"})
    # 検証
    assert result == ["/r/doc.md"]


@pytest.mark.parametrize(
    "tool_input",
    [
        pytest.param({"filter": {"field": "id"}}, id="optional_omitted"),
        pytest.param({"filter": {"field": "id"}, "sections": ["例外"]}, id="optional_differs"),
    ],
)
def test_match_read_tool_when_optional_args(
    make_entry: Callable[..., Any], tool_input: dict[str, Any]
) -> None:
    """`optional_args` は省いても違う値でも照合する（正常系）。"""
    # 準備
    read_tool = ReadTool(
        tool="mcp__docs__search_docs",
        args={"filter": {"field": "id"}},
        optional_args={"sections": ["命名"]},
    )
    entries = [make_entry("/r/doc.md", read_tool=read_tool)]
    # 実行
    result = match_read_tool(entries, "mcp__docs__search_docs", tool_input)
    # 検証
    assert result == ["/r/doc.md"]


def test_match_read_tool_when_duplicate(make_entry: Callable[..., Any]) -> None:
    """同じルールのエントリを 1 件にまとめる（正常系）。"""
    # 準備
    read_tool = ReadTool(tool="mcp__docs__search_docs", args={}, optional_args={})
    entries = [
        make_entry("/r/doc.md", read_tool=read_tool),
        make_entry("/r/doc.md", read_tool=read_tool),
    ]
    # 実行
    result = match_read_tool(entries, "mcp__docs__search_docs", {})
    # 検証
    assert result == ["/r/doc.md"]


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        pytest.param({"c": 2, "a": [1, {"b": True}]}, True, id="key_order_differs"),
        pytest.param({"a": [{"b": True}, 1], "c": 2}, False, id="array_order_differs"),
        pytest.param({"a": [1, {"b": 1}], "c": 2}, False, id="bool_to_number"),
    ],
)
def test_json_equal(actual: Any, expected: bool) -> None:
    """型を区別して入れ子まで比べる（正常系）。"""
    # 準備
    written = {"a": [1, {"b": True}], "c": 2}
    # 実行
    result = _json_equal(written, actual)
    # 検証
    assert result is expected


def test_rule_locations(make_entry: Callable[..., Any]) -> None:
    """重なりを落とした集合を返却する（正常系）。"""
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
    assert result.regex is not None
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
    """正規表現は部分一致で該当する（正常系）。"""
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
    """無いキーは空を返却する（正常系）。"""
    # 実行
    result = _argument_values({"a": "x"}, "a.b")
    # 検証
    assert result == []


def test_argument_values_when_tree() -> None:
    """道筋の値を条件の木として読む（正常系）。"""
    # 準備
    tool_input = {
        "filter": {
            "or": [
                {"field": "tags", "op": "in", "values": ["a", 1]},
                {"field": "kind", "op": "eq", "values": ["rule"]},
            ]
        }
    }
    # 実行
    result = _argument_values(tool_input, "filter", "tags")
    # 検証
    assert result == ["a", "1"]


def test_argument_values_when_tree_in_array() -> None:
    """道筋の値が配列のときは要素ごとに条件の木として読む（正常系）。"""
    # 準備
    tool_input = {
        "filters": [
            {"field": "tags", "op": "in", "values": ["a"]},
            {"field": "tags", "op": "in", "values": ["b"]},
        ]
    }
    # 実行
    result = _argument_values(tool_input, "filters", "tags")
    # 検証
    assert result == ["a", "b"]


def test_match_args_when_empty() -> None:
    """条件が空なら該当する（正常系）。"""
    # 実行
    result = _match_args([], {})
    # 検証
    assert result is True


def test_match_args_when_tree(index_conditions: Callable[..., Any]) -> None:
    """入れ子の and・or の中の条件の値に該当する（正常系）。"""
    # 準備
    conditions = index_conditions({"filter[tags]": ["python"]})
    tool_input = {
        "filter": {
            "and": [
                {"field": "kind", "op": "eq", "values": ["rule"]},
                {"or": [{"field": "tags", "op": "in", "values": ["python"]}]},
            ]
        }
    }
    # 実行
    result = _match_args(conditions, tool_input)
    # 検証
    assert result is True


def test_match_args_when_tree_negated_only(index_conditions: Callable[..., Any]) -> None:
    """条件の木の否定の中にだけある値には照合しない（正常系）。"""
    # 準備
    conditions = index_conditions({"filter[tags]": ["python"]})
    tool_input = {"filter": {"not": {"field": "tags", "op": "in", "values": ["python"]}}}
    # 実行
    result = _match_args(conditions, tool_input)
    # 検証
    assert result is False


def test_read_index(
    make_index: Callable[..., Path],
) -> None:
    """エントリごとの位置・バージョン・状態を返却する（正常系）。"""
    from rule_inject.features.index import entry_rev, read_index

    # 準備
    index = make_index(
        "rules:\n"
        "  - rule: /r/a.md\n"
        '    paths: ["**/*.py"]\n'
        "  - rule: /r/off.md\n"
        "    enabled: false\n"
        "  - rule: https://example.com/a.md\n"
    )
    # 実行
    content = read_index(str(index), {})
    # 検証
    assert content.path == str(index)
    assert [outcome.position for outcome in content.outcomes] == [0, 1, 2]
    assert [outcome.status for outcome in content.outcomes] == ["effective", "disabled", "skipped"]
    assert content.outcomes[0].entry is not None
    assert content.outcomes[0].entry.location == "/r/a.md"
    assert content.outcomes[1].entry is None
    assert "https://example.com/a.md" in (content.outcomes[2].reason or "")
    assert all(outcome.rev == entry_rev(outcome.raw) for outcome in content.outcomes)


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("missing", id="missing"),
        pytest.param("broken", id="broken"),
    ],
)
def test_read_index_when_unreadable(
    tmp_path: Path,
    make_index: Callable[..., Path],
    kind: str,
) -> None:
    """読めない索引を拒む（異常系）。"""
    from rule_inject.features.index import read_index

    # 準備
    index = (
        tmp_path / "missing.yaml"
        if kind == "missing"
        else make_index("rules:\n  - rule: /r/a.md\n   paths: [x]\n", "broken.yaml")
    )
    # 実行・検証
    with pytest.raises(IndexReadError) as raised:
        read_index(str(index), {})
    assert raised.value.path == str(index)


def test_entry_rev_when_format_differs() -> None:
    """書式だけの違いでは変わらない（正常系）。"""
    from rule_inject.features.index import entry_rev
    from rule_inject.features.index._yaml import parse_index

    # 準備
    single = "rules:\n  - rule: 'a.md'\n    paths: ['**/*.py']\n    on: [write]\n"
    double = 'rules:\n  - on: [write]\n    paths: ["**/*.py"]\n    rule: "a.md"\n'
    first = parse_index(single)[1][0]
    second = parse_index(double)[1][0]
    # 実行
    rev_first = entry_rev(first)
    rev_second = entry_rev(second)
    # 検証
    assert len(rev_first) == 12
    assert rev_first == rev_second


def test_entry_rev_when_value_differs() -> None:
    """値が違えば変わる（正常系）。"""
    from rule_inject.features.index import entry_rev
    from rule_inject.features.index._yaml import parse_index

    # 準備
    first = parse_index('rules:\n  - rule: a.md\n    paths: ["**/*.py"]\n')[1][0]
    second = parse_index('rules:\n  - rule: a.md\n    paths: ["**/*.ts"]\n')[1][0]
    # 実行
    rev_first = entry_rev(first)
    rev_second = entry_rev(second)
    # 検証
    assert rev_first != rev_second


def test_read_index_text_when_unparsable() -> None:
    """フックが読めない内容を拒む（異常系）。"""
    from rule_inject.features.index import read_index_text

    # 準備
    text = "rules:\n  - rule: /r/a.md\n   paths: [x]\n"
    # 実行・検証
    with pytest.raises(IndexReadError) as raised:
        read_index_text("/p/index.yaml", text, {})
    assert raised.value.path == "/p/index.yaml"
    assert "3行目" in raised.value.reason


def test_read_index_text_when_tree_key() -> None:
    """引数のキーを道筋と条件の木の field に分ける（正常系）。"""
    from rule_inject.features.index import read_index_text

    # 準備
    text = (
        "rules:\n"
        "  - rule: /r/a.md\n"
        "    args:\n"
        '      filter[tags]: ["a"]\n'
        '      filter.kind: ["rule"]\n'
        '      a[b]c: ["x"]\n'
        "    read_by:\n"
        '      - tools: ["t"]\n'
        "        args:\n"
        '          filter[tags]: ["a"]\n'
    )
    # 実行
    entry = read_index_text("/p/index.yaml", text, {}).outcomes[0].entry
    # 検証
    assert entry is not None
    assert [(c.key, c.path, c.field) for c in entry.args] == [
        ("filter[tags]", "filter", "tags"),
        ("filter.kind", "filter.kind", None),
        ("a[b]c", "a[b]c", None),
    ]
    assert [(c.key, c.path, c.field) for c in entry.read_by[0].args] == [
        ("filter[tags]", "filter", "tags"),
    ]


def test_entry_revs(
    tmp_path: Path,
) -> None:
    """一覧と同じバージョンを返却する（正常系）。"""
    from rule_inject.features.index import entry_revs, read_index_text

    # 準備
    text = (
        "rules:\n"
        '  - rule: "a\\tb.md"\n'
        "  - rule: b.md\n"
        "    paths: [010, 0x1F]\n"
        "  - rule: c.md\n"
        "    tools: [~]\n"
    )
    index_path = str(tmp_path / "index.yaml")
    # 実行
    revs = entry_revs(text)
    # 検証
    outcomes = read_index_text(index_path, text, {}).outcomes
    assert revs == tuple(outcome.rev for outcome in outcomes)
    assert len(revs) == 3


def test_entry_revs_when_unparsable() -> None:
    """フックが読めない内容を拒む（異常系）。"""
    from rule_inject.features.index import entry_revs

    # 準備
    text = "rules:\n  - rule: /r/a.md\n   paths: [x]\n"
    # 実行・検証
    with pytest.raises(ValueError, match="3行目"):
        entry_revs(text)


def test_entry_matches_path(make_entry: Callable[..., Any]) -> None:
    """該当するパスと除外するパスを見分ける（正常系）。"""
    from rule_inject.features.index.service import entry_matches_path

    # 準備
    entry = make_entry("/r/python.md", paths=["**/*.py"], exclude=["**/tests/**"])
    # 実行
    matched = entry_matches_path(entry, "/p/src/a.py")
    excluded = entry_matches_path(entry, "/p/tests/a.py")
    # 検証
    assert matched is True
    assert excluded is False


@pytest.mark.parametrize(
    ("source", "value", "expected"),
    [
        pytest.param("m*", "mcp", True, id="glob_whole"),
        pytest.param("m*", "xm", False, id="glob_not_whole"),
        pytest.param("re:yth", "python", True, id="regex_partial"),
    ],
)
def test_match_arg_pattern(source: str, value: str, expected: bool) -> None:
    """glob は全体、正規表現は部分に照合する（正常系）。"""
    from rule_inject.features.index.service import match_arg_pattern

    # 準備
    regex = re.compile(source.removeprefix("re:")) if source.startswith("re:") else None
    pattern = MatchPattern(source=source, regex=regex)
    # 実行
    result = match_arg_pattern(pattern, value)
    # 検証
    assert result is expected


def test_tree_values_when_nested() -> None:
    """入れ子の and・or の中の条件も取り出す（正常系）。"""
    from rule_inject.features.index.service import _tree_values

    # 準備
    node = {
        "and": [
            {"field": "tags", "op": "in", "values": ["a"]},
            {
                "or": [
                    {"field": "tags", "op": "eq", "values": ["b"]},
                    {"field": "kind", "op": "eq", "values": ["rule"]},
                ]
            },
        ]
    }
    # 実行
    result = _tree_values(node, "tags")
    # 検証
    assert result == ["a", "b"]


def test_tree_values_when_negated() -> None:
    """not の中と否定の op の条件は取らない（正常系）。"""
    from rule_inject.features.index.service import _tree_values

    # 準備
    node = {
        "and": [
            {"not": {"field": "tags", "op": "in", "values": ["a"]}},
            {"field": "tags", "op": "ne", "values": ["b"]},
            {"field": "tags", "op": "not_contains", "values": ["c"]},
            {"field": "tags", "op": "not_exists", "values": ["d"]},
            {"field": "tags", "op": "in", "values": ["e"]},
        ]
    }
    # 実行
    result = _tree_values(node, "tags")
    # 検証
    assert result == ["e"]


@pytest.mark.parametrize(
    "node",
    [
        pytest.param("tags", id="string"),
        pytest.param({"tags": ["a"]}, id="no_field_no_group"),
        pytest.param({"and": "x"}, id="group_not_array"),
    ],
)
def test_tree_values_when_not_tree(node: Any) -> None:
    """条件の木として読めない値からは取らない（正常系）。"""
    from rule_inject.features.index.service import _tree_values

    # 実行
    result = _tree_values(node, "tags")
    # 検証
    assert result == []
