"""既読の記録（PostToolUse）。Read・Bash で全体を読んだルールと、MCP のツールの結果に載った全文のルールの場所（書式に従う文書が無ければ `read_by` に当たったルールの場所）を、本文のハッシュと一緒に既読にし、既読の履歴へ残す。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.features.command import FULL_READ_COMMANDS, extract_read_paths
from rule_inject.features.document import DocumentScope, extract_documents
from rule_inject.features.guidance import build_failure_notice
from rule_inject.features.index import load_indexes, match_read_by, rule_locations
from rule_inject.features.index.types import IndexEntry
from rule_inject.features.record import (
    ReadMethod,
    append_history,
    append_record,
    hash_locations,
    is_valid_session_id,
)
from rule_inject.hooks.rule_guide import MCP_TOOL_PREFIX
from rule_inject.shared.errors import HistoryWriteError, RecordWriteError, RuleInjectError
from rule_inject.shared.logger import Component, LogOperation, log_file_path, write_log
from rule_inject.shared.paths import log_dir, resolve_location, state_dir

URL_SCHEMES = ("http://", "https://")


def _is_whole_file(tool_response: object) -> bool:
    """Read の `tool_response.file` が、ファイルの先頭から最後までを読んだ結果かを返す。"""
    file_info = tool_response.get("file") if isinstance(tool_response, Mapping) else None
    if not isinstance(file_info, Mapping):
        return False
    start_line = file_info.get("startLine")
    num_lines = file_info.get("numLines")
    total_lines = file_info.get("totalLines")
    # 3 つとも bool でない整数のときだけ、先頭から行数がそろっているかを比べる
    if not all(type(value) is int for value in (start_line, num_lines, total_lines)):
        return False
    return start_line == 1 and num_lines == total_lines


def _read_paths(payload: Mapping[str, Any]) -> list[str]:
    """全体を読んだパスを決める（Read は先頭から最後まで読んだ file_path、Bash は全体を読むコマンドの引数）。"""
    tool_input = payload["tool_input"]
    cwd = Path(payload["cwd"])
    if payload["tool_name"] == "Read":
        file_path = tool_input.get("file_path")
        if not file_path or not _is_whole_file(payload.get("tool_response")):
            return []
        return [resolve_location(file_path, cwd)]
    return extract_read_paths(tool_input.get("command", ""), cwd, FULL_READ_COMMANDS)


def _document_paths(payload: Mapping[str, Any]) -> list[str] | None:
    """MCP のツールの結果の全文の文書のパスを解いて返す（書式に従う文書が無ければ None）。"""
    documents = extract_documents(payload.get("tool_response"))
    if not documents:
        return None
    cwd = Path(payload["cwd"])
    return [
        resolve_location(document.path, cwd)
        for document in documents
        if document.scope == DocumentScope.FULL and not document.path.startswith(URL_SCHEMES)
    ]


def _locations_and_method(
    payload: Mapping[str, Any], entries: tuple[IndexEntry, ...]
) -> tuple[list[str], ReadMethod]:
    """既読にする場所と読み方を決める。MCP のツールは結果の全文の文書、無ければ `read_by` に当たるエントリのルールの場所。それ以外は索引に載ったルールのパスだけ。"""
    tool_name = payload["tool_name"]
    listed = rule_locations(entries)
    if tool_name.startswith(MCP_TOOL_PREFIX):
        paths = _document_paths(payload)
        # 書式に従う文書が無い結果は、`read_by` に当たる呼び出しで判断する
        if paths is None:
            return match_read_by(
                entries, tool_name, payload.get("tool_input") or {}
            ), ReadMethod.MCP
        return [path for path in dict.fromkeys(paths) if path in listed], ReadMethod.MCP
    # Read・Bash: 索引に載ったルールの場所と同じパスだけ
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
    tool_name = payload["tool_name"]
    locations, method = _locations_and_method(payload, load_indexes(env).entries)
    # 本文のハッシュを取れない場所は既読にしない
    read_entries = hash_locations(locations)
    if not read_entries:
        return None
    locations = [entry.location for entry in read_entries]
    folder = state_dir(env)
    log_folder = log_dir(env)
    try:
        append_record(folder, session_id, read_entries)
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
