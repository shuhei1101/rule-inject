"""hooks/work_rules.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.hooks._runner import SETTINGS_FAILURE_SUMMARY
from rule_inject.hooks.work_rules import work_rules


def test_work_rules(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """圧縮の後でなければ何も返却しない（正常系）。"""
    # 準備
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = work_rules(payload, hook_env)
    # 検証
    assert result is None


def test_work_rules_when_record_left_after_compact(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    log_folder: Path,
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """圧縮の後の削除できずに残った記録を通知する（正常系）。"""
    # 準備
    record_file = write_record(["/r/a.md"])
    payload = hook_payload("SessionStart", source="compact")
    # 実行
    result = work_rules(payload, hook_env)
    # 検証
    assert result is not None
    output = result["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart"
    context = output["additionalContext"]
    assert context.startswith("圧縮の前に既読の記録を削除できませんでした。")
    assert str(record_file) in context
    assert str(log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log") in context
    assert "Write" not in context


def test_work_rules_when_no_record_after_compact(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """圧縮の後でも記録が無ければ何も返却しない（正常系）。"""
    # 準備
    payload = hook_payload("SessionStart", source="compact")
    # 実行
    result = work_rules(payload, hook_env)
    # 検証
    assert result is None


def test_work_rules_when_settings_unreadable_after_compact(
    unreadable_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    default_log_folder: Path,
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """圧縮の後に設定ファイルが読めなければ理由を通知する（正常系）。"""
    # 準備
    env = unreadable_env("missing")
    payload = hook_payload("SessionStart", source="compact")
    # 実行
    result = work_rules(payload, env)
    # 検証
    assert result is not None
    context = result["hookSpecificOutput"]["additionalContext"]
    assert context.startswith(SETTINGS_FAILURE_SUMMARY)
    assert env["RULE_INJECT_CONFIG"] in context
    assert str(default_log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log") in context
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"


def test_work_rules_when_settings_unreadable_at_startup(
    unreadable_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    default_log_folder: Path,
) -> None:
    """圧縮の後でなければ設定ファイルを読まない（正常系）。"""
    # 準備
    env = unreadable_env("missing")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = work_rules(payload, env)
    # 検証
    assert result is None
    assert not default_log_folder.exists()
