"""features/index/_yaml.py の単体テスト。"""

from __future__ import annotations

import pytest

from rule_inject.features.index._yaml import parse_index

INDEX_WITH_TWO_ENTRIES = """\
# 索引のコメント
default_on: [write]
rules:
  - rule: ./a.md   # 行末のコメント
    paths:
      - "**/*.py"
      - '**/*.pyi'
    on: [read, write]

  - rule: "b#1.md"
    tools: ["mcp__*__create_*"]
"""


def test_parse_index() -> None:
    """フローとブロックのリスト、引用符、コメントを読む（正常系）。"""
    # 実行
    default_on, entries = parse_index(INDEX_WITH_TWO_ENTRIES)
    # 検証
    assert default_on == ("write",)
    assert entries == [
        {"rule": "./a.md", "paths": ["**/*.py", "**/*.pyi"], "on": ["read", "write"]},
        {"rule": "b#1.md", "tools": ["mcp__*__create_*"]},
    ]


def test_parse_index_when_no_default_on() -> None:
    """`default_on` が無ければ None を返す（正常系）。"""
    # 実行
    default_on, entries = parse_index("rules:\n  - rule: ./a.md\n")
    # 検証
    assert default_on is None
    assert entries == [{"rule": "./a.md"}]


def test_parse_index_when_unknown_key() -> None:
    """許さないキーを拒む（異常系）。"""
    # 準備
    text = "rules:\n  - rule: ./a.md\n    foo: bar\n"
    # 実行・検証
    with pytest.raises(ValueError, match="3行目"):
        parse_index(text)


def test_parse_index_when_rule_missing() -> None:
    """`rule` の無いエントリを拒む（異常系）。"""
    # 準備
    text = "rules:\n  - paths: ['**/*.py']\n"
    # 実行・検証
    with pytest.raises(ValueError, match="行目"):
        parse_index(text)


def test_parse_index_when_invalid_on() -> None:
    """`on` の外の値を拒む（異常系）。"""
    # 準備
    text = "rules:\n  - rule: ./a.md\n    on: [delete]\n"
    # 実行・検証
    with pytest.raises(ValueError, match="行目"):
        parse_index(text)


def test_parse_index_when_args() -> None:
    """`args` のブロックのマップを読む（正常系）。"""
    # 準備
    text = (
        "rules:\n"
        "  - rule: ./a.md\n"
        '    tools: ["mcp__*__search_*"]\n'
        "    args:\n"
        '      tags: ["re:^python$"]\n'
        "      filter.kind:\n"
        "        - rule\n"
    )
    # 実行
    _, entries = parse_index(text)
    # 検証
    assert entries == [
        {
            "rule": "./a.md",
            "tools": ["mcp__*__search_*"],
            "args": {"tags": ["re:^python$"], "filter.kind": ["rule"]},
        },
    ]


def test_parse_index_when_args_flow_map() -> None:
    """`args` のフローのマップを拒む（異常系）。"""
    # 準備
    text = "rules:\n  - rule: ./a.md\n    args: {tags: [a]}\n"
    # 実行・検証
    with pytest.raises(ValueError, match="3行目"):
        parse_index(text)


def test_parse_index_when_read_by() -> None:
    """`read_by` のマップのリストを読む（正常系）。"""
    # 準備
    text = (
        "rules:\n"
        "  - rule: ./a.md\n"
        "    read_by:\n"
        "      - tools: [mcp__docs__get_doc]\n"
        "        args:\n"
        '          path: ["re:\\\\.md$"]\n'
        "      - tools:\n"
        "          - mcp__docs__search\n"
    )
    # 実行
    _, entries = parse_index(text)
    # 検証
    assert entries == [
        {
            "rule": "./a.md",
            "read_by": [
                {"tools": ["mcp__docs__get_doc"], "args": {"path": ["re:\\.md$"]}},
                {"tools": ["mcp__docs__search"]},
            ],
        },
    ]


def test_parse_index_when_read_by_without_tools() -> None:
    """`tools` の無い `read_by` の要素を拒む（異常系）。"""
    # 準備
    text = "rules:\n  - rule: ./a.md\n    read_by:\n      - args:\n          path: [a]\n"
    # 実行・検証
    with pytest.raises(ValueError, match="行目"):
        parse_index(text)


def test_parse_index_when_enabled() -> None:
    """`enabled` を読む（正常系）。"""
    # 準備
    text = (
        "rules:\n"
        "  - rule: ./a.md\n"
        "    enabled: false\n"
        "  - rule: ./b.md\n"
        "    enabled: true\n"
        "  - rule: ./c.md\n"
    )
    # 実行
    _, entries = parse_index(text)
    # 検証
    assert entries == [
        {"rule": "./a.md", "enabled": "false"},
        {"rule": "./b.md", "enabled": "true"},
        {"rule": "./c.md"},
    ]


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("no", id="not_boolean"),
        pytest.param("[false]", id="list"),
    ],
)
def test_parse_index_when_invalid_enabled(value: str) -> None:
    """`enabled` の `true` / `false` 以外の値を拒む（異常系）。"""
    # 準備
    text = f"rules:\n  - rule: ./a.md\n    enabled: {value}\n"
    # 実行・検証
    with pytest.raises(ValueError, match="3行目"):
        parse_index(text)
