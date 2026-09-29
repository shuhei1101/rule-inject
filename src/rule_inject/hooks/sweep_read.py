"""既読の記録の掃除（SessionStart）。保持期間を過ぎた別のセッションの記録ファイルを消す。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rule_inject.features.record import is_valid_session_id, sweep_records
from rule_inject.shared.logger import Component, LogOperation, write_log
from rule_inject.shared.paths import state_dir


def sweep_read(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """保持期間を過ぎた別のセッションの記録ファイルを消し、消せなかったものをログへ書く。"""
    session_id = payload.get("session_id")
    # 形が外れた session_id では、始まったセッションを見分けられないため何も消さない
    if not is_valid_session_id(session_id):
        return
    folder = state_dir(env)
    # 消せなかった記録ファイルごとにログへ書く（セッションの開始は止めない）
    for failure in sweep_records(folder, session_id):
        write_log(
            folder,
            component=Component.SWEEP_READ,
            operation=LogOperation.DELETE_RECORD,
            reason=failure.reason,
            session_id=session_id,
            path=failure.path,
        )
