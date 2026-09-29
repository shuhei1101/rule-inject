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
