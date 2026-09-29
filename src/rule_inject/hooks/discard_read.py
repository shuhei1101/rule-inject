"""既読の記録の破棄（PreCompact）。圧縮の前にそのセッションの記録ファイルを消す。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rule_inject.features.record import delete_record, is_valid_session_id
from rule_inject.shared.errors import RecordDeleteError
from rule_inject.shared.logger import Component, LogOperation, write_log
from rule_inject.shared.paths import state_dir


def discard_read(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """そのセッションの記録ファイルを消す（消せなくても圧縮は止めない）。"""
    session_id = payload.get("session_id")
    # 形が外れた session_id では何も消さない
    if not is_valid_session_id(session_id):
        return
    folder = state_dir(env)
    try:
        delete_record(folder, session_id)
    except RecordDeleteError as exc:
        # 消し残りは、圧縮の後の作業の決まりの注入が見つけて知らせる
        write_log(
            folder,
            component=Component.DISCARD_READ,
            operation=LogOperation.DELETE_RECORD,
            reason=exc.reason,
            session_id=session_id,
            path=exc.path,
        )
