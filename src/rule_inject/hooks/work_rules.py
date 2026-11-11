"""圧縮の後の通知（SessionStart）。圧縮の前に削除できずに残った既読の記録と、設定ファイルが読めない理由を知らせる。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from rule_inject.features.record import is_valid_session_id, record_exists
from rule_inject.hooks._runner import settings_failure_notice
from rule_inject.shared.errors import SettingsReadError
from rule_inject.shared.logger import Component, log_file_path
from rule_inject.shared.settings import load_settings

COMPACT_SOURCE = "compact"
LEFTOVER_NOTICE = (
    "圧縮の前に既読の記録を削除できませんでした。"
    "読んだことになっているルールが案内されない場合があります。"
    "記録ファイル: {record}。ログ: {log}"
)


def work_rules(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any] | None:
    """圧縮の後に、削除できずに残った記録か設定ファイルが読めない理由を知らせる。知らせが無ければ None を返す。"""
    session_id = payload.get("session_id")
    # 圧縮の後に始まったときだけ確かめる。それ以外は設定ファイルも読まずに何も返さない
    if payload.get("source") != COMPACT_SOURCE or not is_valid_session_id(session_id):
        return None
    try:
        settings = load_settings(env)
    except SettingsReadError as exc:
        # 設定ファイルが読めなければ、既定値でも動かさず、理由を知らせる
        notice = settings_failure_notice(Component.WORK_RULES, exc, env, session_id)
        return _context(notice)
    folder = settings.state_dir
    # 削除できずに残った記録ファイルがあるか
    if not record_exists(folder, session_id):
        # 無い: 知らせることが無い
        return None
    # ある: 記録ファイルとログの場所を知らせる
    log_path = log_file_path(settings.log_dir, datetime.now(UTC).date())
    return _context(LEFTOVER_NOTICE.format(record=folder / f"{session_id}.txt", log=log_path))


def _context(text: str) -> dict[str, Any]:
    """SessionStart の additionalContext の出力にする。"""
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
