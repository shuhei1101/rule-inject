"""既読の記録の掃除（SessionStart フック）の結合テスト。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


def test_normal(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
    write_guided: Callable[..., Path],
    write_history: Callable[..., Path],
    set_age_days: Callable[[Path, int], Path],
    state_dir: Path,
) -> None:
    """保持期間を過ぎた既読の記録ファイル・案内済みの記録ファイル・既読の履歴ファイルだけを消す（正常系）。"""
    # 準備
    expired = set_age_days(write_record(["/r/a.md"], "expired-session"), 31)
    within = set_age_days(write_record(["/r/b.md"], "within-session"), 29)
    expired_guided = set_age_days(write_guided(["/r/a.md"], "expired-session"), 31)
    within_guided = set_age_days(write_guided(["/r/b.md"], "within-session"), 29)
    not_record = state_dir / "a b.txt"
    not_record.write_text("メモ\n", encoding="utf-8")
    set_age_days(not_record, 31)
    not_guided = state_dir / "a b.guided.txt"
    not_guided.write_text("メモ\n", encoding="utf-8")
    set_age_days(not_guided, 31)
    expired_history = set_age_days(write_history("expired-session"), 31)
    within_history = set_age_days(write_history("within-session"), 29)
    not_history = state_dir / "a b.history.jsonl"
    not_history.write_text("メモ\n", encoding="utf-8")
    set_age_days(not_history, 31)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert not expired.exists()
    assert not expired_guided.exists()
    assert within.exists()
    assert within_guided.exists()
    assert not_record.exists()
    assert not_guided.exists()
    assert not expired_history.exists()
    assert within_history.exists()
    assert not_history.exists()
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_own_record_old(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
    set_age_days: Callable[[Path, int], Path],
) -> None:
    """始まったセッション自身の記録ファイルは、保持期間を過ぎていても消さない（正常系）。"""
    # 準備
    own = set_age_days(write_record(["/r/a.md"]), 31)
    other = set_age_days(write_record(["/r/b.md"], "other-session"), 31)
    payload = hook_payload("SessionStart", source="resume")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert own.exists()
    assert not other.exists()
    assert completed.returncode == 0


def test_normal_when_no_state_dir(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
) -> None:
    """記録フォルダがまだ無くても正常に終える（正常系）。"""
    # 準備
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert not state_dir.exists()
    assert completed.returncode == 0


def test_error_when_record_undeletable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[[Sequence[str], str], Path],
    set_age_days: Callable[[Path, int], Path],
    state_dir: Path,
    log_folder: Path,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """記録を消せず、ログにも書けないとき、セッションの開始は止めずに標準エラー出力に書く（異常系）。"""
    # 準備
    expired = set_age_days(write_record(["/r/a.md"], "expired-session"), 31)
    unwritable(state_dir, 0o555)
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert completed.stdout == ""
    assert '"component": "sweep_read"' in completed.stderr
    assert '"operation": "delete_record"' in completed.stderr
    assert expired.exists()
    assert completed.returncode == 0


def test_normal_when_old_logs(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_dated_log: Callable[[date], Path],
    log_folder: Path,
) -> None:
    """日付が保持日数以上前のログのファイルだけを消す（正常系）。"""
    # 準備
    today = datetime.now(UTC).date()
    today_log = write_dated_log(today)
    within_log = write_dated_log(today - timedelta(days=2))
    expired_log = write_dated_log(today - timedelta(days=3))
    notes = log_folder / "notes.txt"
    notes.write_text("メモ\n", encoding="utf-8")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert not expired_log.exists()
    assert within_log.exists()
    assert today_log.exists()
    assert notes.exists()
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_retention_env(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
    set_age_days: Callable[[Path, int], Path],
    write_dated_log: Callable[[date], Path],
) -> None:
    """環境変数で指した保持の値で、記録ファイルとログのファイルを消す（正常系）。"""
    # 準備
    expired_record = set_age_days(write_record(["/r/a.md"], "expired-session"), 2)
    today = datetime.now(UTC).date()
    today_log = write_dated_log(today)
    expired_log = write_dated_log(today - timedelta(days=1))
    payload = hook_payload("SessionStart", source="startup")
    extra_env = {
        "RULE_INJECT_RECORD_RETENTION_DAYS": "1",
        "RULE_INJECT_LOG_RETENTION_DAYS": "1",
    }
    # 実行
    completed = run_hook("sweep_read", payload, extra_env=extra_env)
    # 検証
    assert not expired_record.exists()
    assert not expired_log.exists()
    assert today_log.exists()
    assert completed.returncode == 0


def test_error_when_log_undeletable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_dated_log: Callable[[date], Path],
    log_folder: Path,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """ログを消せず、ログにも書けないとき、セッションの開始は止めずに標準エラー出力に書く（異常系）。"""
    # 準備
    expired_log = write_dated_log(datetime.now(UTC).date() - timedelta(days=3))
    unwritable(log_folder, 0o555)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert completed.stdout == ""
    assert '"component": "sweep_read"' in completed.stderr
    assert '"operation": "delete_log"' in completed.stderr
    assert expired_log.exists()
    assert completed.returncode == 0


def test_normal_when_legacy_log(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
) -> None:
    """記録フォルダに残った変更前のログを、最終更新によらず消す（正常系）。"""
    # 準備
    state_dir.mkdir()
    legacy_log = state_dir / "rule-inject.log"
    legacy_log.write_text("{}\n", encoding="utf-8")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert not legacy_log.exists()
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_invalid_setting(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_dated_log: Callable[[date], Path],
) -> None:
    """環境変数の保持の値が 1 以上の整数でないときは、既定の値で掃除する（正常系）。"""
    # 準備
    today = datetime.now(UTC).date()
    today_log = write_dated_log(today)
    within_log = write_dated_log(today - timedelta(days=2))
    expired_log = write_dated_log(today - timedelta(days=3))
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload, extra_env={"RULE_INJECT_LOG_RETENTION_DAYS": "0"})
    # 検証
    assert not expired_log.exists()
    assert within_log.exists()
    assert today_log.exists()
    assert completed.returncode == 0
