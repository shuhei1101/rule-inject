"""features/guidance/service.py の単体テスト。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rule_inject.features.guidance.service import (
    BLOCKING_HEADER,
    NON_BLOCKING_HEADER,
    build_failure_notice,
    build_guidance,
)
from rule_inject.features.index.types import MatchedRule
from rule_inject.shared.errors import IndexReadError


@pytest.fixture
def hundred_rules() -> list[MatchedRule]:
    """1 件 150 字前後の場所を持つルール 100 件（止めるものと止めないものが交互）。"""
    return [
        MatchedRule(location=f"/rules/{number:03d}/" + "x" * 137, blocking=number % 2 == 0)
        for number in range(100)
    ]


def test_build_guidance_when_blocking() -> None:
    """止める案内は止めるルールを先に並べる（正常系）。"""
    # 準備
    rules = [
        MatchedRule(location="/r/read.md", blocking=False),
        MatchedRule(location="/r/write.md", blocking=True),
    ]
    # 実行
    result = build_guidance(rules)
    # 検証
    assert result.startswith(BLOCKING_HEADER)
    assert result.index("/r/write.md") < result.index("/r/read.md")


def test_build_guidance_when_not_blocking() -> None:
    """止めない案内は「やり直してください」を含まない（正常系）。"""
    # 準備
    rules = [MatchedRule(location="/r/read.md", blocking=False)]
    # 実行
    result = build_guidance(rules)
    # 検証
    assert result.startswith(NON_BLOCKING_HEADER)
    assert "やり直してください" not in result


def test_build_guidance_when_too_long(hundred_rules: list[MatchedRule]) -> None:
    """上限を超える分を件数にする（正常系）。"""
    # 実行
    result = build_guidance(hundred_rules, limit=10000)
    # 検証
    assert len(result) <= 10000
    assert re.search(r"ほか \d+ 件のルールは", result)


def test_build_failure_notice() -> None:
    """場所と理由を並べる（正常系）。"""
    # 準備
    errors = [
        IndexReadError(path="/i/a.yaml", reason="FileNotFoundError: no such file"),
        IndexReadError(path="/i/b.yaml", reason="ValueError: 3行目: 許さないキー"),
    ]
    # 実行
    result = build_failure_notice("索引を読めませんでした", errors, Path("/s/rule-inject.log"))
    # 検証
    assert "索引を読めませんでした" in result
    assert "- /i/a.yaml: FileNotFoundError: no such file" in result
    assert "- /i/b.yaml: ValueError: 3行目: 許さないキー" in result
    assert "/s/rule-inject.log" in result
