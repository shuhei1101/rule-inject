"""ルール案内（PreToolUse）。操作の対象に該当する未読のルールを案内する。"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.features.command import READ_COMMANDS, extract_read_paths
from rule_inject.features.guidance import (
    GUIDANCE_LIMIT,
    GUIDED_READ_FAILURE,
    GUIDED_WRITE_FAILURE,
    INDEX_FAILURE,
    RECORD_READ_FAILURE,
    Guidance,
    build_failure_notice,
    build_guidance,
)
from rule_inject.features.index import (
    load_indexes,
    match_path,
    match_tool,
    merge_matched,
    rule_locations,
)
from rule_inject.features.index.types import IndexEntry, MatchedRule, Operation
from rule_inject.features.record import (
    append_guided,
    current_read_locations,
    is_valid_session_id,
    read_guided,
    read_record,
)
from rule_inject.hooks._runner import settings_failure_notice
from rule_inject.shared.errors import RecordReadError, RecordWriteError, SettingsReadError
from rule_inject.shared.logger import Component, LogOperation, log_file_path, write_log
from rule_inject.shared.paths import resolve_location
from rule_inject.shared.settings import load_settings

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
    """操作の対象のパスかツール名に該当するルールを、ルールごとに 1 件へまとめて返却する。"""
    tool_name = payload["tool_name"]
    if tool_name.startswith(MCP_TOOL_PREFIX):
        return match_tool(entries, tool_name, payload["tool_input"])
    if tool_name not in TOOL_OPERATIONS:
        return []
    operation = TOOL_OPERATIONS[tool_name]
    targets = _target_paths(payload, tool_name)
    matches: list[MatchedRule] = []
    for path in targets:
        matches.extend(match_path(entries, path, operation))
    merged = merge_matched(matches)
    # 読む操作は、ルールのファイル自身を読むことをそのルールの未読で止めない
    if operation == "read" and targets:
        return _exempt_rule_reads(merged, targets, entries)
    return merged


def _exempt_rule_reads(
    matched: Sequence[MatchedRule], targets: Sequence[str], entries: Sequence[IndexEntry]
) -> list[MatchedRule]:
    """読む対象と同じ場所のルールを除き、対象が全てルールのファイルなら残りを止めない案内にする。"""
    # シンボリックリンクを解いた場所で比べる
    real_targets = {os.path.realpath(target) for target in targets}
    real_locations = {os.path.realpath(location) for location in rule_locations(entries)}
    # 読む対象と同じ場所のルールは案内しない（読んだ後に既読の記録が既読にする）
    remaining = [rule for rule in matched if os.path.realpath(rule.location) not in real_targets]
    # 対象が全てルールのファイルのとき: ほかにヒットしたルールは止めずに案内する（互いのファイルにヒットするルールも読める）
    if real_targets <= real_locations:
        return [dataclasses.replace(rule, blocking=False) for rule in remaining]
    # ルールでないファイルも読むとき: 自身を除いた残りを今までどおり照合した結果のまま返却する
    return remaining


def _log_record_failure(
    log_folder: Path,
    operation: LogOperation,
    session_id: str,
    failure: RecordReadError | RecordWriteError,
) -> None:
    """記録の読み込み・書き込みの失敗をログへ書き込む（操作は止めない）。"""
    write_log(
        log_folder,
        component=Component.RULE_GUIDE,
        operation=operation,
        reason=failure.reason,
        session_id=session_id,
        path=failure.path,
    )


def guide_rules(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any] | None:
    """操作の対象に該当する未読のルールを案内する PreToolUse の出力を作る。"""
    raw_session_id = payload.get("session_id")
    # 形式に合わない session_id は記録の読み込み・書き込みに使用せず、None として扱う
    session_id = raw_session_id if is_valid_session_id(raw_session_id) else None
    # 設定ファイルが読めなければ、既定値でも動かさず、照合せずに止めない通知だけを返却する
    try:
        settings = load_settings(env)
    except SettingsReadError as exc:
        notice = settings_failure_notice(Component.RULE_GUIDE, exc, env, session_id)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": notice}}
    folder = settings.state_dir
    log_folder = settings.log_dir
    log_path = log_file_path(log_folder, datetime.now(UTC).date())
    notices: list[str] = []
    # 読めない索引と読み飛ばしたエントリは、ログと通知の文に回して、読めたエントリでの案内は続ける
    loaded = load_indexes(settings.indexes, env)
    for failure in loaded.failures:
        write_log(
            log_folder,
            component=Component.RULE_GUIDE,
            operation=LogOperation.READ_INDEX,
            reason=failure.reason,
            session_id=session_id,
            path=failure.path,
        )
    if loaded.failures:
        notices.append(build_failure_notice(INDEX_FAILURE, loaded.failures, log_path))
    matched = _match(payload, loaded.entries)
    # そのセッションで読んだルールを除く（読んだ後に本文が変わったルールは未読のまま残す）。記録が読めなければ止めずに理由を通知する
    already_read: frozenset[str] = frozenset()
    record_failed = False
    if session_id is not None and matched:
        try:
            already_read = current_read_locations(
                read_record(folder, session_id), [rule.location for rule in matched]
            )
        except RecordReadError as exc:
            record_failed = True
            _log_record_failure(log_folder, LogOperation.READ_RECORD, session_id, exc)
            notices.append(build_failure_notice(RECORD_READ_FAILURE, [exc], log_path))
    unread = [rule for rule in matched if rule.location not in already_read]
    if record_failed:
        # 既読か分からないため、止めずに案内する
        unread = [dataclasses.replace(rule, blocking=False) for rule in unread]
    # 止めるルールが無いときは、このセッションで案内済みの場所を除く（読めなければ未案内として扱う）
    track_guided = bool(unread) and not any(rule.blocking for rule in unread)
    if session_id is not None and track_guided:
        try:
            guided = read_guided(folder, session_id)
        except RecordReadError as exc:
            guided = frozenset()
            _log_record_failure(log_folder, LogOperation.READ_RECORD, session_id, exc)
            notices.append(build_failure_notice(GUIDED_READ_FAILURE, [exc], log_path))
        unread = [rule for rule in unread if rule.location not in guided]
    if not unread and not notices:
        return None
    guidance = _build(unread, notices)
    # 止めない案内に記載した場所だけを案内済みにする。書き込めなければ案内は出して理由を通知する
    if session_id is not None and track_guided and guidance is not None and guidance.shown:
        try:
            append_guided(folder, session_id, guidance.shown)
        except RecordWriteError as exc:
            _log_record_failure(log_folder, LogOperation.WRITE_RECORD, session_id, exc)
            notices.append(build_failure_notice(GUIDED_WRITE_FAILURE, [exc], log_path))
            # 通知の分を除いた字数に、案内を再度収める
            guidance = _build(unread, notices)
    return _output(guidance, unread, notices)


def _build(unread: Sequence[MatchedRule], notices: Sequence[str]) -> Guidance | None:
    """通知の分を除いた字数に収めた案内文を組み立てる（未読のルールが無ければ None）。"""
    if not unread:
        return None
    budget = GUIDANCE_LIMIT - (
        len(NOTICE_SEPARATOR) + len(NOTICE_SEPARATOR.join(notices)) if notices else 0
    )
    return build_guidance(unread, limit=budget)


def _output(
    guidance: Guidance | None, unread: Sequence[MatchedRule], notices: Sequence[str]
) -> dict[str, Any]:
    """案内と通知から、止める出力か止めない出力を作る。"""
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
