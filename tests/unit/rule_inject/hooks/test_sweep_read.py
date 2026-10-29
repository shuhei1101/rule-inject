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
    """保持期間を過ぎた記録を削除する（正常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    sweep_read(payload, hook_env)
    # 検証
    assert not expired.exists()


def test_sweep_read_when_invalid_session_id(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_aged_record: Callable[..., Path],
) -> None:
    """session_id の形式が外れていれば何も削除しない（正常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31)
    payload = hook_payload("SessionStart", source="startup", session_id="../x")
    # 実行
    sweep_read(payload, hook_env)
    # 検証
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
    """削除できず、ログにも書けないとき標準エラー出力に書く（正常系）。"""
    # 準備
    write_aged_record("expired-session", 31)
    unwritable(state_dir, 0o555)
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    sweep_read(payload, hook_env)
    # 検証
    entry = json.loads(capsys.readouterr().err)
    assert entry["component"] == "sweep_read"
    assert entry["operation"] == "delete_record"


def test_sweep_read_when_old_logs(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_dated_log: Callable[[date], Path],
) -> None:
    """保持日数を過ぎたログのファイルを削除する（正常系）。"""
    # 準備
    today = datetime.now(UTC).date()
    today_log = write_dated_log(today)
    expired_log = write_dated_log(today - timedelta(days=3))
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    sweep_read(payload, hook_env)
    # 検証
    assert not expired_log.exists()
    assert today_log.exists()


def test_sweep_read_when_retention_configured(
    settings_env: Callable[..., dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_aged_record: Callable[..., Path],
    write_dated_log: Callable[[date], Path],
) -> None:
    """設定ファイルの保持の日数で、記録ファイルとログのファイルを削除する（正常系）。"""
    # 準備
    env = settings_env(record_retention_days=1, log_retention_days=1)
    expired_record = write_aged_record("expired-session", 2)
    today = datetime.now(UTC).date()
    today_log = write_dated_log(today)
    expired_log = write_dated_log(today - timedelta(days=1))
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    sweep_read(payload, env)
    # 検証
    assert not expired_record.exists()
    assert not expired_log.exists()
    assert today_log.exists()


def test_sweep_read_when_legacy_log(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
) -> None:
    """変更前のログを削除する（正常系）。"""
    # 準備
    state_dir.mkdir()
    legacy_log = state_dir / "rule-inject.log"
    legacy_log.write_text("{}\n", encoding="utf-8")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    sweep_read(payload, hook_env)
    # 検証
    assert not legacy_log.exists()


def test_sweep_read_when_settings_unreadable(
    unreadable_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    default_log_folder: Path,
) -> None:
    """設定ファイルが読めないときはログに書くだけで何も削除しない（正常系）。"""
    # 準備
    env = unreadable_env("retention_zero")
    today = datetime.now(UTC).date()
    default_log_folder.mkdir(parents=True)
    expired_log = default_log_folder / f"{today - timedelta(days=3):%Y%m%d}_rule-inject.log"
    expired_log.write_text("{}\n", encoding="utf-8")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    sweep_read(payload, env)
    # 検証
    assert expired_log.exists()
    today_log = default_log_folder / f"{today:%Y%m%d}_rule-inject.log"
    logged = [json.loads(line) for line in today_log.read_text(encoding="utf-8").splitlines()]
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"


def test_sweep_read_when_guided(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_aged_record: Callable[..., Path],
) -> None:
    """保持期間を過ぎた案内済みの記録も削除する（正常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31, suffix=".guided.txt")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    sweep_read(payload, hook_env)
    # 検証
    assert not expired.exists()
