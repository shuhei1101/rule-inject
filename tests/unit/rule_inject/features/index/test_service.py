"""features/index/service.py の単体テスト。"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.index import load_indexes, match_path, match_tool, rule_locations
from rule_inject.features.index.service import (
    _argument_values,
    _compile_pattern,
    _glob_match,
    _match_pattern,
    select_locations,
)
from rule_inject.features.index.types import MatchedRule, MatchPattern


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


def test_load_indexes_when_no_env(tmp_path: Path) -> None:
    """環境変数が無く、既定の置き場所にも索引が無ければ何も読まない（正常系）。"""
    # 準備
    config_home = tmp_path / "config"
    project = tmp_path / "project"
    config_home.mkdir()
    project.mkdir()
    env = {"XDG_CONFIG_HOME": str(config_home), "CLAUDE_PROJECT_DIR": str(project)}
    # 実行
    result = load_indexes(env)
    # 検証
    assert not result.entries
    assert not result.failures


def test_load_indexes_when_default(
    tmp_path: Path,
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """環境変数が無ければ既定の置き場所を読む（正常系）。"""
    # 準備
    make_index(index_text("/r/user.md"), "config/rule-inject/rules.yaml")
    make_index(index_text("/r/project.md"), "project/rules.yaml")
    env = {
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "CLAUDE_PROJECT_DIR": str(tmp_path / "project"),
    }
    # 実行
    result = load_indexes(env)
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/user.md", "/r/project.md"]
    assert not result.failures


def test_load_indexes_when_default_config_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """`XDG_CONFIG_HOME` が無ければ `~/.config` の下を読む（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    make_index(index_text("/r/home.md"), "home/.config/rule-inject/rules.yaml")
    # 実行
    result = load_indexes({})
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/home.md"]
    assert not result.failures


def test_load_indexes_when_env_empty(
    tmp_path: Path,
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> None:
    """空の文字列の環境変数は既定の置き場所も読まない（正常系）。"""
    # 準備
    make_index(index_text("/r/user.md"), "config/rule-inject/rules.yaml")
    make_index(index_text("/r/project.md"), "project/rules.yaml")
    env = {
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "CLAUDE_PROJECT_DIR": str(tmp_path / "project"),
        "RULE_INJECT_INDEXES_PROJECT": "",
    }
    # 実行
    result = load_indexes(env)
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/user.md"]
    assert not result.failures


def test_load_indexes_when_rule_has_variable(
    tmp_path: Path,
    make_index: Callable[..., Path],
) -> None:
    """`rule` の変数参照を展開してから解く（正常系）。"""
    # 準備
    index = make_index('rules:\n  - rule: "!{RULES}/a.md"\n  - rule: "./!{SUB}/b.md"\n')
    env = {
        "RULE_INJECT_INDEXES_PROJECT": str(index),
        "RULES": "/r",
        "SUB": "s",
    }
    # 実行
    result = load_indexes(env)
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/a.md", str(tmp_path / "s" / "b.md")]
    assert not result.failures


def test_load_indexes_when_rule_variable_unset(
    make_index: Callable[..., Path],
) -> None:
    """展開できないエントリだけを読み飛ばす（正常系）。"""
    # 準備
    index = make_index('rules:\n  - rule: "!{UNSET}/a.md"\n  - rule: /r/ok.md\n')
    env = {"RULE_INJECT_INDEXES_PROJECT": str(index)}
    # 実行
    result = load_indexes(env)
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
    env = {"RULE_INJECT_INDEXES_PROJECT": str(index)}
    # 実行
    result = load_indexes(env)
    # 検証
    assert [entry.location for entry in result.entries] == ["/r/ok.md"]
    assert result.entries[0].paths[0].regex.pattern == "\\.py$"
    assert result.entries[0].args[0].key == "kind"
    assert result.entries[0].args[0].patterns[0].source == "rule"
    assert len(result.failures) == 1
    assert result.failures[0].path == str(index)
    assert "re:[" in result.failures[0].reason


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


def test_select_locations(make_entry: Callable[..., Any]) -> None:
    """索引に載った場所を選ぶ（正常系）。"""
    # 準備
    entries = [make_entry("/r/a.md"), make_entry("https://example.com/b.md")]
    # 実行
    result = select_locations(entries, ["/r/a.md", "https://example.com/b.md"], [])
    # 検証
    assert result.targets == ("/r/a.md", "https://example.com/b.md")
    assert result.rejected == ()


def test_select_locations_when_by_path(make_entry: Callable[..., Any]) -> None:
    """対象のパスで引く（正常系）。"""
    # 準備
    entries = [
        make_entry("/r/py.md", paths=["**/*.py"]),
        make_entry("/r/ts.md", paths=["**/*.ts"]),
    ]
    # 実行
    result = select_locations(entries, ["/r/py.md"], ["/p/src/a.py"])
    # 検証
    assert result.targets == ("/r/py.md",)
    assert result.rejected == ()


def test_select_locations_when_not_in_index(make_entry: Callable[..., Any]) -> None:
    """索引に無い場所は読まない（正常系）。"""
    # 準備
    entries = [make_entry("/r/listed.md")]
    # 実行
    result = select_locations(entries, ["/r/unlisted.md", "https://example.com/x.md"], [])
    # 検証
    assert result.targets == ()
    assert len(result.rejected) == 2
    assert "索引に載っていない場所" in result.rejected[0].reason
    assert "索引に載っていない場所" in result.rejected[1].reason


def test_select_locations_when_relative(make_entry: Callable[..., Any]) -> None:
    """相対パスは解かない（正常系）。"""
    # 準備
    entries = [make_entry("/r/a.md", paths=["**/*.py"])]
    # 実行
    result = select_locations(entries, ["rules/a.md"], ["src/a.py"])
    # 検証
    assert result.targets == ()
    assert len(result.rejected) == 2
    assert "相対パス" in result.rejected[0].reason
    assert "相対パス" in result.rejected[1].reason


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
