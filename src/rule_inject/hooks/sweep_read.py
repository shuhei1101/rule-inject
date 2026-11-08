"""既読の記録の掃除（SessionStart）。保持期間を過ぎた記録ファイルと古いログを消す。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rule_inject.features.record import is_valid_session_id, sweep_records
from rule_inject.hooks._runner import log_settings_failure
from rule_inject.shared.errors import RuleInjectError, SettingsReadError
from rule_inject.shared.logger import (
    Component,
    LogOperation,
    delete_legacy_log,
    sweep_logs,
    write_log,
)
from rule_inject.shared.settings import load_settings


def _log_failure(
    log_folder: Path,
    operation: LogOperation,
    session_id: str,
    failure: RuleInjectError,
) -> None:
    """消せなかった失敗をログへ書く（セッションの開始は止めない）。"""
    write_log(
        log_folder,
        component=Component.SWEEP_READ,
        operation=operation,
        reason=failure.reason,
        session_id=session_id,
        path=failure.path,
    )


def sweep_read(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """保持期間を過ぎた記録ファイル・変更前のログ・保持日数を過ぎたログを消し、失敗をログへ書く。"""
    session_id = payload.get("session_id")
    # 形が外れた session_id では、始まったセッションを見分けられないため何も消さない
    if not is_valid_session_id(session_id):
        return
    # 設定ファイルが読めなければ、既定値でも動かさず、ログに書いて何も消さない
    try:
        settings = load_settings(env)
    except SettingsReadError as exc:
        log_settings_failure(Component.SWEEP_READ, exc, env, session_id)
        return
    state_folder = settings.state_dir
    log_folder = settings.log_dir
    # 保持期間を過ぎた別のセッションの記録ファイルを消す
    for record_failure in sweep_records(
        state_folder, session_id, retention_days=settings.record_retention_days
    ):
        _log_failure(log_folder, LogOperation.DELETE_RECORD, session_id, record_failure)
    # 記録フォルダに残った変更前のログを消す
    legacy_failure = delete_legacy_log(state_folder)
    if legacy_failure is not None:
        _log_failure(log_folder, LogOperation.DELETE_LOG, session_id, legacy_failure)
    # 日付が保持日数以上前のログのファイルを消す
    for log_failure in sweep_logs(log_folder, settings.log_retention_days):
        _log_failure(log_folder, LogOperation.DELETE_LOG, session_id, log_failure)
