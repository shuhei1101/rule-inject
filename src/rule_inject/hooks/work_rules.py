"""作業の決まりの注入（SessionStart）。新しいファイルは空で作ってから書く決まりを載せる。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from rule_inject.features.guidance import WORK_RULES
from rule_inject.features.record import is_valid_session_id, record_exists
from rule_inject.hooks._runner import settings_failure_notice
from rule_inject.shared.errors import SettingsReadError
from rule_inject.shared.logger import Component, log_file_path
from rule_inject.shared.settings import load_settings

COMPACT_SOURCE = "compact"
LEFTOVER_NOTICE = (
    "圧縮の前に既読の記録を消せませんでした。"
    "読んだことになっているルールが案内されない場合があります。"
    "記録ファイル: {record}。ログ: {log}"
)


def work_rules(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    """作業の決まりを返し、圧縮の後に記録が残っていれば消せなかったことも返す。"""
    text = WORK_RULES
    session_id = payload.get("session_id")
    # 圧縮の後に始まったときだけ、消し残った記録ファイルを確かめる
    if payload.get("source") == COMPACT_SOURCE and is_valid_session_id(session_id):
        try:
            settings = load_settings(env)
        except SettingsReadError as exc:
            # 設定ファイルが読めなければ、既定値でも動かさず、作業の決まりに理由を続ける
            notice = settings_failure_notice(Component.WORK_RULES, exc, env, session_id)
            text = f"{text}\n\n{notice}"
        else:
            folder = settings.state_dir
            if record_exists(folder, session_id):
                log_path = log_file_path(settings.log_dir, datetime.now(UTC).date())
                leftover = LEFTOVER_NOTICE.format(record=folder / f"{session_id}.txt", log=log_path)
                text = f"{text}\n\n{leftover}"
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
