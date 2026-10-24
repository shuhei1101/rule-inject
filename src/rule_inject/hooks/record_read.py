"""既読の記録（PostToolUse）。Read・Bash で読んだルールと、`read_by` に当たった MCP のツールのルールの場所を既読にし、既読の履歴へ残す。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.features.command import FULL_READ_COMMANDS, extract_read_paths
from rule_inject.features.guidance import build_failure_notice
from rule_inject.features.index import load_indexes, match_read_by, rule_locations
from rule_inject.features.index.types import IndexEntry
from rule_inject.features.record import (
    ReadMethod,
    append_history,
    append_record,
    is_valid_session_id,
)
from rule_inject.hooks.rule_guide import MCP_TOOL_PREFIX, OWN_TOOL_PREFIX
from rule_inject.shared.errors import HistoryWriteError, RecordWriteError, RuleInjectError
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


def _locations_and_method(
    payload: Mapping[str, Any], entries: tuple[IndexEntry, ...]
) -> tuple[list[str], ReadMethod]:
    """既読にする場所と読み方を決める。MCP のツールは `read_by` に当たるエントリのルールの場所、それ以外は索引に載ったルールのパスだけ。"""
    tool_name = payload["tool_name"]
    # MCP のツール: read_by のツール名と引数に当たるエントリのルールの場所
    if tool_name.startswith(MCP_TOOL_PREFIX):
        return match_read_by(entries, tool_name, payload.get("tool_input") or {}), ReadMethod.MCP
    # Read・Bash: 索引に載ったルールの場所と同じパスだけ
    listed = rule_locations(entries)
    locations = [path for path in dict.fromkeys(_read_paths(payload)) if path in listed]
    return locations, ReadMethod.READ if tool_name == "Read" else ReadMethod.BASH


def _failure_context(summary: str, error: RuleInjectError, log_path: Path) -> dict[str, Any]:
    """書けなかった理由を載せた additionalContext を作る。"""
    notice = build_failure_notice(summary, [error], log_path)
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": notice}}


def record_read(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any] | None:
    """既読にする場所を既読の記録と既読の履歴へ書き、書けなければ理由を返す。"""
    session_id = payload.get("session_id")
    if not is_valid_session_id(session_id):
        return None
    # このプラグイン自身のツールは、`read_rules` が既読と履歴を書く
    tool_name = payload["tool_name"]
    if tool_name.startswith(OWN_TOOL_PREFIX):
        return None
    locations, method = _locations_and_method(payload, load_indexes(env).entries)
    if not locations:
        return None
    folder = state_dir(env)
    log_folder = log_dir(env)
    try:
        append_record(folder, session_id, locations)
    except RecordWriteError as exc:
        write_log(
            log_folder,
            component=Component.RECORD_READ,
            operation=LogOperation.WRITE_RECORD,
            reason=exc.reason,
            session_id=session_id,
            path=exc.path,
        )
        summary = f"次のルールを既読にできませんでした（{', '.join(locations)}）。"
        return _failure_context(summary, exc, log_file_path(log_folder, datetime.now(UTC).date()))
    try:
        append_history(folder, session_id, locations, method=method, tool=tool_name)
    except HistoryWriteError as exc:
        # 既読の記録は残したまま、履歴にだけ書けなかったことを知らせる
        write_log(
            log_folder,
            component=Component.RECORD_READ,
            operation=LogOperation.WRITE_HISTORY,
            reason=exc.reason,
            session_id=session_id,
            path=exc.path,
        )
        summary = f"次のルールを既読にしましたが、既読の履歴に書けませんでした（{', '.join(locations)}）。"
        return _failure_context(summary, exc, log_file_path(log_folder, datetime.now(UTC).date()))
    return None
