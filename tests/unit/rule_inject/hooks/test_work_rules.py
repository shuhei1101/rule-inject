"""hooks/work_rules.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.features.guidance.service import WORK_RULES
from rule_inject.hooks.work_rules import work_rules


def test_work_rules(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """作業の決まりを返す（正常系）。"""
    # 準備
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = work_rules(payload, hook_env)
    # 検証
    output = result["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart"
    assert output["additionalContext"] == WORK_RULES


def test_work_rules_when_record_left_after_compact(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    log_folder: Path,
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """圧縮の後の消し残りを知らせる（正常系）。"""
    # 準備
    record_file = write_record(["/r/a.md"])
    payload = hook_payload("SessionStart", source="compact")
    # 実行
    result = work_rules(payload, hook_env)
    # 検証
    context = result["hookSpecificOutput"]["additionalContext"]
    assert WORK_RULES in context
    assert str(record_file) in context
    assert str(log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log") in context
