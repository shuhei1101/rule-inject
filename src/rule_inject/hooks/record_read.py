"""既読の記録（PostToolUse）。Read か Bash で読んだルールの場所を既読にする。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.features.command import FULL_READ_COMMANDS, extract_read_paths
from rule_inject.features.guidance import build_failure_notice
from rule_inject.features.index import load_indexes, rule_locations
from rule_inject.features.record import append_record, is_valid_session_id
from rule_inject.shared.errors import RecordWriteError
from rule_inject.shared.logger import Component, LogOperation, log_file_path, write_log
from rule_inject.shared.paths import log_dir, resolve_location, state_dir


def _read_paths(payload: Mapping[str, Any]) -> list[str]:
    """読んだパスを決める（Read は file_path、Bash は全体を読むコマンドの引数）。"""
    tool_input = payload["tool_input"]
    cwd = Path(payload["cwd"])
    if payload["tool_name"] == "Read":
        file_path = tool_input.get("file_path")
        return [resolve_location(file_path, cwd)] if file_path else []
    return extract_read_paths(tool_input.get("command", ""), cwd, FULL_READ_COMMANDS)


def record_read(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any] | None:
    """Read か Bash で読んだルールの場所を既読にし、書けなければ理由を返す。"""
    session_id = payload.get("session_id")
    if not is_valid_session_id(session_id):
        return None
    # 索引に載ったルールの場所と同じパスだけを既読にする
    listed = rule_locations(load_indexes(env).entries)
    locations = [path for path in dict.fromkeys(_read_paths(payload)) if path in listed]
    folder = state_dir(env)
    try:
        append_record(folder, session_id, locations)
    except RecordWriteError as exc:
        log_folder = log_dir(env)
        write_log(
            log_folder,
            component=Component.RECORD_READ,
            operation=LogOperation.WRITE_RECORD,
            reason=exc.reason,
            session_id=session_id,
            path=exc.path,
        )
        summary = f"次のルールを既読にできませんでした（{', '.join(locations)}）。"
        log_path = log_file_path(log_folder, datetime.now(UTC).date())
        notice = build_failure_notice(summary, [exc], log_path)
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": notice}}
    return None
