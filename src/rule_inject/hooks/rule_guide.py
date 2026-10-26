"""ルール案内（PreToolUse）。操作の対象に当たる未読のルールを案内する。"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.features.command import READ_COMMANDS, extract_read_paths
from rule_inject.features.guidance import (
    GUIDANCE_LIMIT,
    Guidance,
    build_failure_notice,
    build_guidance,
)
from rule_inject.features.index import load_indexes, match_path, match_tool
from rule_inject.features.index.types import IndexEntry, MatchedRule, Operation
from rule_inject.features.record import (
    append_guided,
    current_read_locations,
    is_valid_session_id,
    read_guided,
    read_record,
)
from rule_inject.shared.errors import RecordReadError, RecordWriteError
from rule_inject.shared.logger import Component, LogOperation, log_file_path, write_log
from rule_inject.shared.paths import log_dir, resolve_location, state_dir

MCP_TOOL_PREFIX = "mcp__"
# ツール名から操作の種別への対応
TOOL_OPERATIONS: dict[str, Operation] = {
    "Read": "read",
    "Grep": "read",
    "Bash": "read",
    "Edit": "write",
    "Write": "write",
    "NotebookEdit": "write",
}
# ツールの入力のうち、操作の対象のパスを持つキー
PATH_KEYS = {
    "Read": "file_path",
    "Edit": "file_path",
    "Write": "file_path",
    "NotebookEdit": "notebook_path",
}
NOTICE_SEPARATOR = "\n\n"


def _merge(matches: Sequence[MatchedRule]) -> list[MatchedRule]:
    """同じルールの場所を 1 件にまとめ、どれか 1 つでも止めるなら止める（並びは保つ）。"""
    blocking_by_location: dict[str, bool] = {}
    for rule in matches:
        blocking_by_location[rule.location] = (
            blocking_by_location.get(rule.location, False) or rule.blocking
        )
    return [
        MatchedRule(location=location, blocking=blocking)
        for location, blocking in blocking_by_location.items()
    ]


def _target_paths(payload: Mapping[str, Any], tool_name: str) -> list[str]:
    """ツールの入力から、照合する操作の対象の絶対パスを取り出す。"""
    tool_input = payload["tool_input"]
    cwd = Path(payload["cwd"])
    # Bash は読むコマンドの引数から取り出す
    if tool_name == "Bash":
        return extract_read_paths(tool_input.get("command", ""), cwd, READ_COMMANDS)
    # Grep は、ファイルを指すときだけ照合する（フォルダは中のどのファイルを読むかが決まらない）
    if tool_name == "Grep":
        target = resolve_location(tool_input.get("path", ""), cwd) if tool_input.get("path") else ""
        return [target] if target and os.path.isfile(target) else []
    raw = tool_input.get(PATH_KEYS[tool_name])
    return [resolve_location(raw, cwd)] if raw else []


def _match(payload: Mapping[str, Any], entries: Sequence[IndexEntry]) -> list[MatchedRule]:
    """操作の対象のパスかツール名に当たるルールを、ルールごとに 1 件へまとめて返す。"""
    tool_name = payload["tool_name"]
    if tool_name.startswith(MCP_TOOL_PREFIX):
        return match_tool(entries, tool_name, payload["tool_input"])
    if tool_name not in TOOL_OPERATIONS:
        return []
    operation = TOOL_OPERATIONS[tool_name]
    matches: list[MatchedRule] = []
    for path in _target_paths(payload, tool_name):
        matches.extend(match_path(entries, path, operation))
    return _merge(matches)


def _log_record_failure(
    log_folder: Path,
    operation: LogOperation,
    session_id: str,
    failure: RecordReadError | RecordWriteError,
) -> None:
    """記録の読み書きの失敗をログへ書く（操作は止めない）。"""
    write_log(
        log_folder,
        component=Component.RULE_GUIDE,
        operation=operation,
        reason=failure.reason,
        session_id=session_id,
        path=failure.path,
    )


def guide_rules(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any] | None:
    """操作の対象に当たる未読のルールを案内する PreToolUse の出力を作る。"""
    folder = state_dir(env)
    log_folder = log_dir(env)
    log_path = log_file_path(log_folder, datetime.now(UTC).date())
    session_id = payload.get("session_id")
    valid_session = is_valid_session_id(session_id)
    notices: list[str] = []
    # 読めない索引と読み飛ばしたエントリは、ログと知らせの文に回して、読めたエントリでの案内は続ける
    loaded = load_indexes(env)
    for failure in loaded.failures:
        write_log(
            log_folder,
            component=Component.RULE_GUIDE,
            operation=LogOperation.READ_INDEX,
            reason=failure.reason,
            session_id=session_id if valid_session else None,
            path=failure.path,
        )
    if loaded.failures:
        notices.append(build_failure_notice("索引を読めませんでした。", loaded.failures, log_path))
    matched = _match(payload, loaded.entries)
    # そのセッションで読んだルールを除く（読んだ後に本文が変わったルールは未読のまま残す）。記録が読めなければ止めずに理由を知らせる
    already_read: frozenset[str] = frozenset()
    record_failed = False
    if valid_session and matched:
        try:
            already_read = current_read_locations(
                read_record(folder, session_id), [rule.location for rule in matched]
            )
        except RecordReadError as exc:
            record_failed = True
            _log_record_failure(log_folder, LogOperation.READ_RECORD, session_id, exc)
            notices.append(build_failure_notice("既読の記録を読めませんでした。", [exc], log_path))
    unread = [rule for rule in matched if rule.location not in already_read]
    if record_failed:
        # 既読か分からないため、止めずに案内する
        unread = [MatchedRule(location=rule.location, blocking=False) for rule in unread]
    # 止めるルールが無いときは、このセッションで案内済みの場所を除く（読めなければ未案内として扱う）
    track_guided = valid_session and bool(unread) and not any(rule.blocking for rule in unread)
    if track_guided:
        try:
            guided = read_guided(folder, session_id)
        except RecordReadError as exc:
            guided = frozenset()
            _log_record_failure(log_folder, LogOperation.READ_RECORD, session_id, exc)
            notices.append(
                build_failure_notice("案内済みの記録を読めませんでした。", [exc], log_path)
            )
        unread = [rule for rule in unread if rule.location not in guided]
    if not unread and not notices:
        return None
    guidance = _build(unread, notices)
    # 止めない案内に載せた場所だけを案内済みにする。書けなければ案内は出して理由を知らせる
    if track_guided and guidance is not None and guidance.shown:
        try:
            append_guided(folder, session_id, guidance.shown)
        except RecordWriteError as exc:
            _log_record_failure(log_folder, LogOperation.WRITE_RECORD, session_id, exc)
            notices.append(
                build_failure_notice("案内済みの記録に書けませんでした。", [exc], log_path)
            )
            # 知らせの分を引いた字数に、案内を収め直す
            guidance = _build(unread, notices)
    return _output(guidance, unread, notices)


def _build(unread: Sequence[MatchedRule], notices: Sequence[str]) -> Guidance | None:
    """知らせの分を引いた字数に収めた案内文を組み立てる（未読のルールが無ければ None）。"""
    if not unread:
        return None
    budget = GUIDANCE_LIMIT - (
        len(NOTICE_SEPARATOR) + len(NOTICE_SEPARATOR.join(notices)) if notices else 0
    )
    return build_guidance(unread, limit=budget)


def _output(
    guidance: Guidance | None, unread: Sequence[MatchedRule], notices: Sequence[str]
) -> dict[str, Any]:
    """案内と知らせから、止める出力か止めない出力を作る。"""
    text = NOTICE_SEPARATOR.join(
        part for part in (guidance.text if guidance else "", *notices) if part
    )
    output: dict[str, Any] = {"hookEventName": "PreToolUse"}
    if any(rule.blocking for rule in unread):
        output["permissionDecision"] = "deny"
        output["permissionDecisionReason"] = text
    else:
        output["additionalContext"] = text
    return {"hookSpecificOutput": output}
