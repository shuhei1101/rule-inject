"""タグのパターンを集め、使われているタグのどれにも当たらないものを返す。"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from typing import Literal

from rule_inject.features.index import match_arg_pattern
from rule_inject.features.index.check.types import TagPattern
from rule_inject.features.index.types import ArgCondition, IndexContent

# 使われているかを確かめる、条件の木のキーの `field`
TAG_FIELD = "tags"
# dev-docs がタグを数える前にかける Unicode の正規化の形式（この後に `casefold` する）
TAG_NORMALIZATION_FORM: Literal["NFKC"] = "NFKC"


def _condition_patterns(
    index: str, position: int, rev: str, location: str, conditions: Sequence[ArgCondition]
) -> list[TagPattern]:
    """条件の並びから、`field` が `TAG_FIELD` のキーのパターンを書いた順に集める。"""
    return [
        TagPattern(
            index=index,
            position=position,
            rev=rev,
            location=location,
            key=condition.key,
            pattern=pattern,
        )
        for condition in conditions
        # ドットの道筋のキー（`field` が None）はタグとみなさない
        if condition.field == TAG_FIELD
        for pattern in condition.patterns
    ]


def tag_patterns(contents: Sequence[IndexContent]) -> tuple[TagPattern, ...]:
    """索引の効いているエントリの `args` と `read_by[].args` から、タグに当てるパターンを集める。"""
    patterns: list[TagPattern] = []
    for content in contents:
        for outcome in content.outcomes:
            # `enabled: false` と読み飛ばしたエントリは見ない
            if outcome.status != "effective" or outcome.entry is None:
                continue
            entry = outcome.entry
            patterns.extend(
                _condition_patterns(content.path, outcome.position, outcome.rev, "args", entry.args)
            )
            for number, condition in enumerate(entry.read_by):
                patterns.extend(
                    _condition_patterns(
                        content.path,
                        outcome.position,
                        outcome.rev,
                        f"read_by[{number}].args",
                        condition.args,
                    )
                )
    return tuple(patterns)


def unused_tag_patterns(
    patterns: Sequence[TagPattern], tags: Sequence[str]
) -> tuple[TagPattern, ...]:
    """使われているタグのどれにも当たらないパターンを、渡された順に返す。"""
    # 照らす値は、返ったタグそのものと、各タグを正規化したもの
    used = {
        *tags,
        *(unicodedata.normalize(TAG_NORMALIZATION_FORM, tag).casefold() for tag in tags),
    }
    # パターンの側は正規化せず、どちらかの値に当たれば使われているとする
    return tuple(
        pattern
        for pattern in patterns
        if not any(match_arg_pattern(pattern.pattern, value) for value in used)
    )
