"""タグのパターンを集め、使用中のタグのどれにも該当しないものを返却する。"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from typing import Literal

from rule_inject.features.index import match_arg_pattern
from rule_inject.features.index.check.types import TagPattern
from rule_inject.features.index.types import ArgCondition, IndexContent

# 使用中のかを確認する、条件の木のキーの `field`
TAG_FIELD = "tags"
# project-index がタグを数える前にかける Unicode の正規化の形式（この後に `casefold` する）
TAG_NORMALIZATION_FORM: Literal["NFKC"] = "NFKC"


def _condition_patterns(
    index: str, position: int, rev: str, location: str, conditions: Sequence[ArgCondition]
) -> list[TagPattern]:
    """条件の並びから、`field` が `TAG_FIELD` のキーのパターンを記載した順に集める。"""
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
    """索引の有効なエントリの `args` と `read_by[].args` から、タグに照合するパターンを集める。"""
    patterns: list[TagPattern] = []
    for content in contents:
        for outcome in content.outcomes:
            # `enabled: false` と読み飛ばしたエントリは確認しない
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
    """使用中のタグのどれにも該当しないパターンを、引き渡された順に返却する。"""
    # 照らす値は、返ったタグそのものと、各タグを正規化したもの
    used = {
        *tags,
        *(unicodedata.normalize(TAG_NORMALIZATION_FORM, tag).casefold() for tag in tags),
    }
    # パターンの側は正規化せず、どちらかの値に該当すれば使用中のとする
    return tuple(
        pattern
        for pattern in patterns
        if not any(match_arg_pattern(pattern.pattern, value) for value in used)
    )
