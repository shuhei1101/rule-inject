"""索引のチェックのツールの本体と、続きの位置の文字列の変換。"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from jsonschema.protocols import Validator
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult

from rule_inject.features.index import read_index
from rule_inject.features.index.check import (
    ScanCursor,
    TagPattern,
    check_index,
    scan_unmatched,
    tag_patterns,
    unused_tag_patterns,
)
from rule_inject.features.index.check.types import IndexCheck, IndexProblem
from rule_inject.features.index.types import IndexContent
from rule_inject.server._format import respond
from rule_inject.server.dev_docs import UsedTags, fetch_used_tags
from rule_inject.server.tools import _config_path, _project_settings
from rule_inject.server.types import (
    CheckIndexesResult,
    IndexReport,
    ResponseFormat,
    TagCheckReport,
    UnmatchedScanReport,
)
from rule_inject.shared.errors import IndexReadError

# `paths` の当たらないエントリの検出を、続きから辿るための `cursor` の中身のキー
CURSOR_KEYS = (
    "project_dir",
    "include_global",
    "last_file",
    "scanned_files",
    "unmatched",
    "fingerprint",
)


def _encode_scan_cursor(cursor: ScanCursor, project_dir: str, include_global: bool) -> str:
    """続きの位置と、呼び出しの `project_dir`・`include_global` を、1 つの不透明な文字列にする。"""
    payload = {
        "project_dir": project_dir,
        "include_global": include_global,
        "last_file": cursor.last_file,
        "scanned_files": cursor.scanned_files,
        "unmatched": [list(key) for key in cursor.unmatched],
        "fingerprint": cursor.fingerprint,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return encoded.decode("ascii").rstrip("=")


def _cursor_error(reason: str) -> ToolError:
    """`cursor` が使えないことを、直し方を添えた ToolError にする。"""
    return ToolError(
        f"cursor が使えません（{reason}）。cursor を省いて最初から辿るか、"
        "前の呼び出しと同じ project_dir・include_global で渡してください"
    )


def _is_entry_key(value: Any) -> bool:
    """確かめるエントリの索引・位置・バージョンの組か。"""
    return (
        isinstance(value, list)
        and len(value) == len(("index", "position", "rev"))
        and isinstance(value[0], str)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)
        and isinstance(value[2], str)
    )


def _decode_scan_cursor(cursor: str, project_dir: str, include_global: bool) -> ScanCursor:
    """`_encode_scan_cursor` の文字列を続きの位置に戻し、呼び出しの `project_dir`・`include_global` と合うかを確かめる。"""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except ValueError as exc:
        raise _cursor_error("読めない文字列") from exc
    # 項目の型を確かめる
    if (
        not isinstance(payload, dict)
        or any(key not in payload for key in CURSOR_KEYS)
        or not isinstance(payload["project_dir"], str)
        or not isinstance(payload["include_global"], bool)
        or not isinstance(payload["last_file"], str)
        or not isinstance(payload["scanned_files"], int)
        or isinstance(payload["scanned_files"], bool)
        or not isinstance(payload["unmatched"], list)
        or not all(_is_entry_key(key) for key in payload["unmatched"])
        or not isinstance(payload["fingerprint"], str)
    ):
        raise _cursor_error("項目が足りないか型が違う")
    # 前の呼び出しと違う引数では続きから辿れない
    if payload["project_dir"] != project_dir or payload["include_global"] != include_global:
        raise _cursor_error("project_dir か include_global が前の呼び出しと違う")
    return ScanCursor(
        last_file=payload["last_file"],
        scanned_files=payload["scanned_files"],
        unmatched=tuple((key[0], key[1], key[2]) for key in payload["unmatched"]),
        fingerprint=payload["fingerprint"],
    )


def _report(index: str, origin: Literal["global", "project"], check: IndexCheck) -> IndexReport:
    """索引 1 つの問題を、種類ごとの一覧に分けた応答にする。"""
    problems = check.problems
    return IndexReport(
        index=index,
        origin=origin,
        hook_error=next(
            (problem.reason for problem in problems if problem.kind == "hook_error"), None
        ),
        violations=[
            {"location": problem.location, "reason": problem.reason}
            for problem in problems
            if problem.kind == "violation"
        ],
        missing_rules=[
            {"position": problem.position, "rule": problem.reason}
            for problem in problems
            if problem.kind == "missing_rule"
        ],
        skipped_entries=[
            {"position": problem.position, "reason": problem.reason}
            for problem in problems
            if problem.kind == "skipped_entry"
        ],
        unmatched_paths=[],
        unused_tag_patterns=[],
    )


def _unmatched_paths(problems: tuple[IndexProblem, ...]) -> list[dict[str, Any]]:
    """`unmatched_path` の問題を、位置・バージョン・解いたルールの場所の一覧にする。"""
    return [
        {"position": problem.position, "rev": problem.rev, "rule": problem.reason}
        for problem in problems
    ]


def _unused_tag_entries(patterns: Sequence[TagPattern]) -> list[dict[str, Any]]:
    """使われていないタグのパターンを、位置・バージョン・場所・キー・書いたままのパターンの一覧にする。"""
    return [
        {
            "position": pattern.position,
            "rev": pattern.rev,
            "location": pattern.location,
            "key": pattern.key,
            "pattern": pattern.pattern.source,
        }
        for pattern in patterns
    ]


async def check_indexes(
    *,
    project_dir: str,
    format: ResponseFormat = "markdown",
    include_global: bool = False,
    cursor: str | None = None,
    env: Mapping[str, str],
    validator: Validator,
    scan_time_limit: float,
    dev_docs_timeout: float,
) -> CallToolResult:
    """プロジェクトで読む索引ごとに、フックが読めない理由・JSON Schema への違反・ルールの場所にファイルが無いエントリ・`paths` の当たらないエントリ・使われていないタグのパターンを返す。"""
    settings = _project_settings(project_dir, env)
    scan_cursor = (
        _decode_scan_cursor(cursor, project_dir, include_global) if cursor is not None else None
    )
    reports: list[IndexReport] = []
    # フックが読めた索引（使われていないタグのパターンは `global` と `project` の全てを確かめる）
    readable: list[IndexContent] = []
    # `paths` の当たらないエントリを確かめる索引（読めた索引のうち `project`、`include_global` なら全て）
    contents: list[IndexContent] = []
    for index in settings.indexes:
        origin: Literal["global", "project"] = (
            "project" if index in settings.project_indexes else "global"
        )
        report = _report(index, origin, check_index(index, env, validator=validator))
        reports.append(report)
        if report.hook_error is None:
            try:
                content = read_index(index, env)
            except IndexReadError:
                # 読み取りの失敗は `hook_error` に載せ済み
                continue
            readable.append(content)
            if origin == "project" or include_global:
                contents.append(content)
    patterns = tag_patterns(readable)
    # dev-docs への問い合わせはファイルを辿る前に始め、辿り終えた後に応答を待つ（問い合わせと辿るのを並べて行う）
    async with asyncio.TaskGroup() as group:
        used_task = (
            group.create_task(
                fetch_used_tags(settings.dev_docs_url, project_dir, timeout=dev_docs_timeout)
            )
            if patterns
            else None
        )
        scan = await asyncio.to_thread(
            scan_unmatched, project_dir, contents, cursor=scan_cursor, time_limit=scan_time_limit
        )
    used: UsedTags | None = used_task.result() if used_task is not None else None
    unmatched_by_index = {check.index: check.problems for check in scan.checks}
    for report in reports:
        report.unmatched_paths = _unmatched_paths(unmatched_by_index.get(report.index, ()))
    # タグの確かめ: パターンが無ければ問い合わせず、引けなければ飛ばし、引けたら使われていないものを索引ごとに載せる
    if used is None:
        tag_check = TagCheckReport(state="no_patterns", reason=None)
    elif used.reason is not None:
        tag_check = TagCheckReport(state="skipped", reason=used.reason)
    else:
        tag_check = TagCheckReport(state="checked", reason=None)
        unused = unused_tag_patterns(patterns, used.tags)
        for report in reports:
            report.unused_tag_patterns = _unused_tag_entries(
                [pattern for pattern in unused if pattern.index == report.index]
            )
    # 問題の件数にユーザー全体の索引の `unmatched_paths` と、どの索引の `unused_tag_patterns` も数えない
    problem_count = sum(
        int(report.hook_error is not None)
        + len(report.violations)
        + len(report.missing_rules)
        + len(report.skipped_entries)
        + (len(report.unmatched_paths) if report.origin == "project" else 0)
        for report in reports
    )
    next_cursor = (
        _encode_scan_cursor(scan.next_cursor, project_dir, include_global)
        if scan.next_cursor is not None
        else None
    )
    result = CheckIndexesResult(
        success=True,
        output=f"索引 {len(reports)} 件・問題 {problem_count} 件",
        config_path=_config_path(env),
        problem_count=problem_count,
        unmatched_scan=UnmatchedScanReport(
            completed=scan.completed,
            scanned_files=scan.scanned_files,
            reason=None
            if scan.completed
            else (
                f"辿る時間の上限（{scan_time_limit:g} 秒）で止まりました。"
                "next_cursor を cursor に渡して呼び直すと、続きから辿ります"
            ),
            next_cursor=next_cursor,
        ),
        tag_check=tag_check,
        indexes=reports,
    )
    return respond(result, format)
