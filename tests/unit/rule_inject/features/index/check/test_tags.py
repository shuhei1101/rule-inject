"""features/index/check/tags.py の単体テスト。"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest

from rule_inject.features.index import read_index_text
from rule_inject.features.index.types import MatchPattern

if TYPE_CHECKING:
    from rule_inject.features.index.check.types import TagPattern

INDEX_PATH = "/p/index.yaml"


@pytest.fixture
def make_tag_pattern() -> Callable[[str], TagPattern]:
    """パターンの文字列から、タグのパターン（位置 0・場所 `args`）を作る factory。"""

    def _make(source: str) -> TagPattern:
        """`re:` で始まるパターンはコンパイルし、それ以外は glob のまま TagPattern にする。"""
        from rule_inject.features.index.check.types import TagPattern

        regex = re.compile(source.removeprefix("re:")) if source.startswith("re:") else None
        return TagPattern(
            index=INDEX_PATH,
            position=0,
            rev="3f9a1c0b2d4e",
            location="args",
            key="filter[tags]",
            pattern=MatchPattern(source=source, regex=regex),
        )

    return _make


def test_tag_patterns(index_text: Callable[..., str]) -> None:
    """条件の木の tags のパターンだけを場所つきで集める（正常系）。"""
    from rule_inject.features.index.check.tags import tag_patterns

    # 準備
    text = index_text(
        "/r/a.md",
        args={"filter[tags]": ["a", "b"], "filter[kind]": ["rule"], "filter.tags": ["c"]},
        read_by=[{"tools": ["x"], "args": {"q[tags]": ["d"]}}],
    )
    content = read_index_text(INDEX_PATH, text, {})
    # 実行
    result = tag_patterns([content])
    # 検証
    assert [(p.location, p.key, p.pattern.source) for p in result] == [
        ("args", "filter[tags]", "a"),
        ("args", "filter[tags]", "b"),
        ("read_by[0].args", "q[tags]", "d"),
    ]
    assert {p.index for p in result} == {INDEX_PATH}
    assert [p.position for p in result] == [0, 0, 0]
    assert {p.rev for p in result} == {content.outcomes[0].rev}


def test_tag_patterns_when_not_effective() -> None:
    """効いていないエントリは集めない（正常系）。"""
    from rule_inject.features.index.check.tags import tag_patterns

    # 準備
    text = (
        "rules:\n"
        "  - rule: /r/off.md\n"
        "    enabled: false\n"
        "    args:\n"
        '      filter[tags]: ["x"]\n'
        '  - rule: "!{UNSET}/skipped.md"\n'
        "    args:\n"
        '      filter[tags]: ["y"]\n'
    )
    content = read_index_text(INDEX_PATH, text, {})
    # 実行
    result = tag_patterns([content])
    # 検証
    assert result == ()


def test_unused_tag_patterns(make_tag_pattern: Callable[[str], TagPattern]) -> None:
    """返ったタグか正規化したタグに当たらないパターンだけを返す（正常系）。"""
    from rule_inject.features.index.check.tags import unused_tag_patterns

    # 準備
    patterns = [
        make_tag_pattern("python"),
        make_tag_pattern("Python"),
        make_tag_pattern("pyhton"),
        make_tag_pattern("m*"),
        make_tag_pattern("re:^kotlin$"),
    ]
    # 実行
    result = unused_tag_patterns(patterns, ["Python", "mcp"])
    # 検証
    assert [p.pattern.source for p in result] == ["pyhton", "re:^kotlin$"]


def test_unused_tag_patterns_when_fullwidth(make_tag_pattern: Callable[[str], TagPattern]) -> None:
    """NFKC で揃うタグに当てる（正常系）。"""
    from rule_inject.features.index.check.tags import unused_tag_patterns

    # 準備
    patterns = [make_tag_pattern("python3")]
    # 実行
    result = unused_tag_patterns(patterns, ["Ｐｙｔｈｏｎ３"])
    # 検証
    assert result == ()
