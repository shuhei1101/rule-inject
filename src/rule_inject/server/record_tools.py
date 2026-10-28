"""既読の記録の確認・削除のツールの本体。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from pydantic import Field

from rule_inject.features.record import (
    HistoryEntry,
    ReadMethod,
    delete_guided,
    delete_record,
    is_valid_session_id,
    list_read_entries,
    list_record_sessions,
    list_rule_states,
    read_history,
)
from rule_inject.server._format import fit_page, respond
from rule_inject.server.tools import (
    CURSOR_PATTERN,
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    _config_path,
)
from rule_inject.server.types import (
    DeleteRecordsResult,
    ReadRecordsResult,
    ReadSummary,
    RecordSessionItem,
    ResponseFormat,
    RuleRead,
)
from rule_inject.shared.errors import (
    RecordDeleteError,
    RecordReadError,
    SettingsReadError,
)
from rule_inject.shared.settings import PROJECT_DIR_ENV, Settings, load_settings

# 既読の記録の確認の `updated_at`（UTC の ISO 8601、秒まで）
UPDATED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _record_settings(env: Mapping[str, str]) -> Settings:
    """`CLAUDE_PROJECT_DIR` 無しで、フックと同じ規則で設定を読む。呼び出しのたびに読み直す。"""
    try:
        return load_settings({key: value for key, value in env.items() if key != PROJECT_DIR_ENV})
    except SettingsReadError as exc:
        raise ToolError(f"{exc.path}: {exc.reason}") from exc


def _check_session_id(session_id: str) -> None:
    """記録ファイル名に使えない形式の `session_id` を ToolError にする（ファイルのパスには使わない）。"""
    if not is_valid_session_id(session_id):
        raise ToolError(
            f"session_id の形式が誤っています（英数字・`_`・`-` の 1〜128 字）: {session_id}"
        )


def _summaries(history: tuple[HistoryEntry, ...]) -> dict[str, list[ReadSummary]]:
    """既読の履歴を、場所ごとに、読み方とツール名の組ごとにまとめる（最後に既読にした時刻の古い順）。"""
    grouped: dict[str, dict[tuple[ReadMethod, str], tuple[str, int]]] = {}
    for entry in history:
        by_read = grouped.setdefault(entry.location, {})
        key = (entry.method, entry.tool)
        last_time, count = by_read.get(key, ("", 0))
        by_read[key] = (max(last_time, entry.time), count + 1)
    return {
        location: [
            ReadSummary(method=method, tool=tool, last_time=last_time, count=count)
            for (method, tool), (last_time, count) in sorted(
                by_read.items(), key=lambda item: item[1][0]
            )
        ]
        for location, by_read in grouped.items()
    }


def get_read_records(
    *,
    session_id: str | None = None,
    limit: Annotated[int, Field(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
    cursor: Annotated[str | None, Field(pattern=CURSOR_PATTERN)] = None,
    format: ResponseFormat = "markdown",
    env: Mapping[str, str],
) -> CallToolResult:
    """セッションの既読のルールごとに、今の本文が既読にした時点と同じかと、読んだ方法を返す。セッションを省くと、既読の記録のあるセッションの一覧を返す。"""
    if session_id is not None:
        _check_session_id(session_id)
    settings = _record_settings(env)
    state_dir = settings.state_dir
    rules: list[RuleRead] = []
    sessions: list[RecordSessionItem] = []
    try:
        if session_id is None:
            sessions = [
                RecordSessionItem(
                    session_id=session.session_id,
                    updated_at=session.updated_at.strftime(UPDATED_AT_FORMAT),
                    rule_count=session.rule_count,
                )
                for session in list_record_sessions(state_dir)
            ]
        else:
            summaries = _summaries(read_history(state_dir, session_id))
            rules = [
                RuleRead(location=location, state=state, reads=summaries.get(location, []))
                for location, state in list_rule_states(list_read_entries(state_dir, session_id))
            ]
    except RecordReadError as exc:
        raise ToolError(f"{exc.path}: {exc.reason}") from exc
    total = len(rules) if session_id is not None else len(sessions)
    start = int(cursor or 0)
    page_rules = rules[start : start + limit]
    page_sessions = sessions[start : start + limit]

    def build(count: int) -> ReadRecordsResult:
        """ページの先頭から count 件を持つ応答を作る。"""
        end = start + count
        return ReadRecordsResult(
            success=True,
            output=(
                f"既読のルール {total} 件"
                if session_id is not None
                else f"既読の記録のあるセッション {total} 件"
            ),
            config_path=_config_path(env),
            state_dir=str(state_dir),
            session_id=session_id,
            rules=page_rules[:count],
            sessions=page_sessions[:count],
            total=total,
            next_cursor=str(end) if end < total else None,
        )

    page_size = len(page_rules) if session_id is not None else len(page_sessions)
    result, _ = fit_page(build, page_size, format)
    return respond(result, format)


def delete_read_records(*, session_id: str, env: Mapping[str, str]) -> CallToolResult:
    """セッションの既読の記録と案内済みの記録をファイルごと削除し、既読だったルールの場所を返す。既読の履歴は削除しない。"""
    _check_session_id(session_id)
    settings = _record_settings(env)
    try:
        locations = list(
            dict.fromkeys(
                entry.location for entry in list_read_entries(settings.state_dir, session_id)
            )
        )
        delete_record(settings.state_dir, session_id)
        delete_guided(settings.state_dir, session_id)
    except (RecordReadError, RecordDeleteError) as exc:
        raise ToolError(f"{exc.path}: {exc.reason}") from exc
    result = DeleteRecordsResult(
        success=True,
        output=f"既読のルール {len(locations)} 件の記録を削除しました",
        config_path=_config_path(env),
        state_dir=str(settings.state_dir),
        session_id=session_id,
        locations=locations,
    )
    return respond(result, "json")
