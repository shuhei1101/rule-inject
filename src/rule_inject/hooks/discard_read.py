"""既読の記録の破棄（PreCompact）。圧縮の前にそのセッションの既読の記録ファイルと案内済みの記録ファイルを削除する。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rule_inject.features.record import delete_guided, delete_record, is_valid_session_id
from rule_inject.hooks._runner import log_settings_failure
from rule_inject.shared.errors import RecordDeleteError, SettingsReadError
from rule_inject.shared.logger import Component, LogOperation, write_log
from rule_inject.shared.settings import load_settings


def discard_read(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """そのセッションの既読の記録ファイルと案内済みの記録ファイルを削除する（削除できなくても圧縮は止めない）。"""
    session_id = payload.get("session_id")
    # 形式が外れた session_id では何も削除しない
    if not is_valid_session_id(session_id):
        return
    # 設定ファイルが読めなければ、既定値でも動かさず、ログに書いて何も削除しない
    try:
        settings = load_settings(env)
    except SettingsReadError as exc:
        log_settings_failure(Component.DISCARD_READ, exc, env, session_id)
        return
    # 片方が削除できなくても、もう片方を削除する
    for delete in (delete_record, delete_guided):
        try:
            delete(settings.state_dir, session_id)
        except RecordDeleteError as exc:
            # 削除できずに残った記録は、圧縮の後の作業の決まりの注入が見つけて知らせる
            write_log(
                settings.log_dir,
                component=Component.DISCARD_READ,
                operation=LogOperation.DELETE_RECORD,
                reason=exc.reason,
                session_id=session_id,
                path=exc.path,
            )
