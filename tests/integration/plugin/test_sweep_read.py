"""既読の記録の掃除（SessionStart フック）の結合テスト。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def test_normal(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
    set_age_days: Callable[[Path, int], Path],
    state_dir: Path,
) -> None:
    """保持期間を過ぎた記録ファイルだけを消す（正常系）。"""
    # 準備
    expired = set_age_days(write_record(["/r/a.md"], "expired-session"), 31)
    within = set_age_days(write_record(["/r/b.md"], "within-session"), 29)
    log_file = state_dir / "rule-inject.log"
    log_file.write_text("{}\n", encoding="utf-8")
    set_age_days(log_file, 31)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert not expired.exists()
    assert within.exists()
    assert log_file.exists()
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
    payload = hook_payload("SessionStart", source="resume")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert own.exists()
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
    unwritable: Callable[[Path, int], Path],
) -> None:
    """記録を消せず、ログにも書けないとき、セッションの開始は止めずに標準エラー出力に書く（異常系）。"""
    # 準備
    expired = set_age_days(write_record(["/r/a.md"], "expired-session"), 31)
    unwritable(state_dir, 0o555)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("sweep_read", payload)
    # 検証
    assert completed.stdout == ""
    assert '"component": "sweep_read"' in completed.stderr
    assert '"operation": "delete_record"' in completed.stderr
    assert expired.exists()
    assert completed.returncode == 0
