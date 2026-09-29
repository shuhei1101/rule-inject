"""hooks/sweep_read.py の単体テスト。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from rule_inject.hooks.sweep_read import sweep_read


def test_sweep_read(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_aged_record: Callable[..., Path],
) -> None:
    """保持期間を過ぎた記録を消す（正常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = sweep_read(payload, hook_env)
    # 検証
    assert result is None
    assert not expired.exists()


def test_sweep_read_when_invalid_session_id(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_aged_record: Callable[..., Path],
) -> None:
    """session_id の形が外れていれば何も消さない（正常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31)
    payload = hook_payload("SessionStart", source="startup", session_id="../x")
    # 実行
    result = sweep_read(payload, hook_env)
    # 検証
    assert result is None
    assert expired.exists()


def test_sweep_read_when_undeletable(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    log_folder: Path,
    write_aged_record: Callable[..., Path],
    unwritable: Callable[[Path, int], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """消せず、ログにも書けないとき標準エラー出力に書く（正常系）。"""
    # 準備
    write_aged_record("expired-session", 31)
    unwritable(state_dir, 0o555)
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = sweep_read(payload, hook_env)
    # 検証
    assert result is None
    entry = json.loads(capsys.readouterr().err)
    assert entry["component"] == "sweep_read"
    assert entry["operation"] == "delete_record"


def test_sweep_read_when_old_logs(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_dated_log: Callable[[date], Path],
) -> None:
    """保持日数を過ぎたログのファイルを消す（正常系）。"""
    # 準備
    today = datetime.now(UTC).date()
    today_log = write_dated_log(today)
    expired_log = write_dated_log(today - timedelta(days=3))
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = sweep_read(payload, hook_env)
    # 検証
    assert result is None
    assert not expired_log.exists()
    assert today_log.exists()


def test_sweep_read_when_retention_env(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_aged_record: Callable[..., Path],
    write_dated_log: Callable[[date], Path],
) -> None:
    """環境変数で指した保持の値で、記録ファイルとログのファイルを消す（正常系）。"""
    # 準備
    env = {
        **hook_env,
        "RULE_INJECT_RECORD_RETENTION_DAYS": "1",
        "RULE_INJECT_LOG_RETENTION_DAYS": "1",
    }
    expired_record = write_aged_record("expired-session", 2)
    today = datetime.now(UTC).date()
    today_log = write_dated_log(today)
    expired_log = write_dated_log(today - timedelta(days=1))
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = sweep_read(payload, env)
    # 検証
    assert result is None
    assert not expired_record.exists()
    assert not expired_log.exists()
    assert today_log.exists()


def test_sweep_read_when_legacy_log(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
) -> None:
    """変更前のログを消す（正常系）。"""
    # 準備
    state_dir.mkdir()
    legacy_log = state_dir / "rule-inject.log"
    legacy_log.write_text("{}\n", encoding="utf-8")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = sweep_read(payload, hook_env)
    # 検証
    assert result is None
    assert not legacy_log.exists()


def test_sweep_read_when_invalid_setting(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_dated_log: Callable[[date], Path],
) -> None:
    """保持の値が不正なら既定の日数で掃除する（正常系）。"""
    # 準備
    env = {**hook_env, "RULE_INJECT_LOG_RETENTION_DAYS": "0"}
    today = datetime.now(UTC).date()
    today_log = write_dated_log(today)
    within_log = write_dated_log(today - timedelta(days=2))
    expired_log = write_dated_log(today - timedelta(days=3))
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = sweep_read(payload, env)
    # 検証
    assert result is None
    assert not expired_log.exists()
    assert within_log.exists()
    assert today_log.exists()
