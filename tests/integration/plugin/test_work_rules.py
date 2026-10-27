"""作業の決まりの注入（SessionStart フック）の結合テスト。"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def test_normal(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """作業の決まりを additionalContext で返す（正常系）。"""
    # 準備
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook("work_rules", payload)
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "空の内容で作り" in context
    assert completed.returncode == 0


def test_normal_when_record_left_after_compact(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[[Sequence[str]], Path],
    log_folder: Path,
) -> None:
    """圧縮の後に記録ファイルが残っていれば、消せなかったことも載せる（正常系）。"""
    # 準備
    record_file = write_record(["/r/a.md"])
    payload = hook_payload("SessionStart", source="compact")
    # 実行
    completed = run_hook("work_rules", payload)
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "空の内容で作り" in context
    assert "消せませんでした" in context
    assert str(record_file) in context
    assert str(log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log") in context
    assert completed.returncode == 0


def test_error_when_settings_unreadable(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """圧縮の後に設定ファイルが読めないとき、作業の決まりに続けて理由を載せる（異常系）。"""
    # 準備
    missing = tmp_path / "config" / "missing.yaml"
    payload = hook_payload("SessionStart", source="compact")
    # 実行
    completed = run_hook(
        "work_rules", payload, no_config=True, extra_env={"RULE_INJECT_CONFIG": str(missing)}
    )
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "空の内容で作り" in context
    assert str(missing) in context
    assert "FileNotFoundError" in context
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"
    assert completed.returncode == 0
