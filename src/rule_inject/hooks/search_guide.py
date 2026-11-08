"""検索結果の案内（PostToolUse）。検索の結果に出たファイルに当たる未読・未案内のルールを案内する。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.features.command import extract_result_paths, search_output_base
from rule_inject.features.guidance import (
    GUIDANCE_LIMIT,
    Guidance,
    build_failure_notice,
    build_search_guidance,
)
from rule_inject.features.index import load_indexes, match_path
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
from rule_inject.shared.settings import load_settings

# 結果を Grep・Glob の形（ファイル名の一覧と一致した行）で受けるツール
SEARCH_TOOLS = ("Grep", "Glob")
BASH_TOOL = "Bash"
NOTICE_SEPARATOR = "\n\n"


def _result_lines(payload: Mapping[str, Any]) -> tuple[list[str], Path] | None:
    """結果の行と、その相対パスを解く基準を返す（検索の結果でなければ None）。"""
    tool_name = payload["tool_name"]
    response = payload.get("tool_response")
    # 結果が辞書で届かなければ、読める行が無い
    if not isinstance(response, Mapping):
        return None
    cwd = Path(payload["cwd"])
    if tool_name in SEARCH_TOOLS:
        # Grep の files_with_matches と Glob は filenames、Grep の content・count は content の各行
        lines = [
            *(response.get("filenames") or ()),
            *str(response.get("content") or "").splitlines(),
        ]
        return lines, cwd
    if tool_name != BASH_TOOL:
        return None
    # Bash は検索のコマンドのときだけ、標準出力の各行を、そのコマンドの出力の基準から解く
    base = search_output_base(payload["tool_input"].get("command", ""), cwd)
    if base is None:
        return None
    return str(response.get("stdout") or "").splitlines(), base


def _log_record_failure(
    log_folder: Path,
    operation: LogOperation,
    session_id: str,
    failure: RecordReadError | RecordWriteError,
) -> None:
    """記録の読み書きの失敗をログへ書く（案内は止めない）。"""
    write_log(
        log_folder,
        component=Component.SEARCH_GUIDE,
        operation=operation,
        reason=failure.reason,
        session_id=session_id,
        path=failure.path,
    )


def _build(locations: Sequence[str], unchecked: int, notices: Sequence[str]) -> Guidance | None:
    """知らせの分を引いた字数に収めた案内文を組み立てる（案内する場所が無ければ None）。"""
    if not locations:
        return None
    budget = GUIDANCE_LIMIT - (
        len(NOTICE_SEPARATOR) + len(NOTICE_SEPARATOR.join(notices)) if notices else 0
    )
    return build_search_guidance(locations, unchecked=unchecked, limit=budget)


def search_guide(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any] | None:
    """検索の結果に出たファイルに当たる未読・未案内のルールを案内する PostToolUse の出力を作る。"""
    session_id = payload.get("session_id")
    # 案内済みを記録できないと毎回同じ案内が出るため、形が外れた session_id では何も出さない
    if not is_valid_session_id(session_id):
        return None
    result_lines = _result_lines(payload)
    if result_lines is None:
        return None
    lines, base = result_lines
    found = extract_result_paths(lines, base)
    if not found.paths:
        return None
    # 設定ファイルが読めなければ、既定値でも動かさず、照合せずに知らせだけを返す
    try:
        settings = load_settings(env)
    except SettingsReadError as exc:
        notice = settings_failure_notice(Component.SEARCH_GUIDE, exc, env, session_id)
        return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": notice}}
    folder = settings.state_dir
    log_folder = settings.log_dir
    log_path = log_file_path(log_folder, datetime.now(UTC).date())
    notices: list[str] = []
    # 読めない索引と読み飛ばしたエントリは、ログと知らせの文に回して、読めたエントリでの案内は続ける
    loaded = load_indexes(settings.indexes, env)
    for failure in loaded.failures:
        write_log(
            log_folder,
            component=Component.SEARCH_GUIDE,
            operation=LogOperation.READ_INDEX,
            reason=failure.reason,
            session_id=session_id,
            path=failure.path,
        )
    if loaded.failures:
        notices.append(build_failure_notice("索引を読めませんでした。", loaded.failures, log_path))
    # 読む操作として当たるルールを、場所ごとに 1 件へまとめる（出た順）
    matched = list(
        dict.fromkeys(
            rule.location
            for path in found.paths
            for rule in match_path(loaded.entries, path, "read")
        )
    )
    # 既読と案内済みを除く（読んだ後に本文が変わったルールは既読にしない）。読めない記録は空として扱い、理由を知らせる
    excluded: set[str] = set()
    if matched:

        def read_current(directory: Path, session: str) -> frozenset[str]:
            """既読の記録のうち、今の本文のハッシュの組がある場所を返す。"""
            return current_read_locations(read_record(directory, session), matched)

        for read, summary in (
            (read_current, "既読の記録を読めませんでした。"),
            (read_guided, "案内済みの記録を読めませんでした。"),
        ):
            try:
                excluded |= read(folder, session_id)
            except RecordReadError as exc:
                _log_record_failure(log_folder, LogOperation.READ_RECORD, session_id, exc)
                notices.append(build_failure_notice(summary, [exc], log_path))
    remaining = [location for location in matched if location not in excluded]
    guidance = _build(remaining, found.unchecked, notices)
    # 案内に載せた場所だけを案内済みにする。書けなければ案内は出して理由を知らせる
    if guidance is not None and guidance.shown:
        try:
            append_guided(folder, session_id, guidance.shown)
        except RecordWriteError as exc:
            _log_record_failure(log_folder, LogOperation.WRITE_RECORD, session_id, exc)
            notices.append(
                build_failure_notice("案内済みの記録に書けませんでした。", [exc], log_path)
            )
            # 知らせの分を引いた字数に、案内を収め直す
            guidance = _build(remaining, found.unchecked, notices)
    text = NOTICE_SEPARATOR.join(
        part for part in (guidance.text if guidance else "", *notices) if part
    )
    if not text:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}
