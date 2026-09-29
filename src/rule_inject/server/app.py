"""stdio の MCP サーバーの入口。read_rules を登録し、索引・本文の取得・既読の記録の機能を順に呼んで組み立てる。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from rule_inject.features.fetch import (
    MAX_RESULT_CHARS,
    FetchFailure,
    FetchUrlFn,
    ReadRulesResult,
    collect_pages,
    fetch_url,
    render_result,
)
from rule_inject.features.index import load_indexes
from rule_inject.features.index.service import select_locations
from rule_inject.features.index.types import IndexEntry
from rule_inject.features.record import append_record, is_valid_session_id
from rule_inject.shared.errors import RecordWriteError, describe
from rule_inject.shared.logger import Component, LogOperation, write_log
from rule_inject.shared.paths import state_dir

SERVER_NAME = "rule-inject"
LOCATIONS_DESCRIPTION = (
    "ルールの場所を渡す。案内に載った場所をそのまま渡す。これから触るファイルのパスは paths へ"
)
PATHS_DESCRIPTION = (
    "触るファイルの絶対パスを渡す。まだ無いパスでもよい。ルールの場所は locations へ"
)
SESSION_ID_DESCRIPTION = "渡さない。フックが足す"


class ToolArgumentError(ValueError):
    """session_id が無い・形が外れている、または locations と paths が空。"""


def read_rules(
    locations: Sequence[str],
    paths: Sequence[str],
    session_id: str | None,
    *,
    entries: Sequence[IndexEntry],
    state_dir: Path,
    fetch: FetchUrlFn = fetch_url,
    limit: int = MAX_RESULT_CHARS,
) -> ReadRulesResult:
    """索引で読む場所を選び、本文を上限に収めて集め、返した場所を既読にする。"""
    # 引数が足りなければ、何も読まずにエラーにする
    if session_id is None or not is_valid_session_id(session_id):
        raise ToolArgumentError("session_id が無いか、形が外れています（フックが足す値です）")
    if not locations and not paths:
        raise ToolArgumentError("locations と paths のどちらかに、場所かパスを渡してください")
    # 読まない場所は理由つきで failures の先頭に載せ、読む場所の本文を集める
    selected = select_locations(entries, locations, paths)
    rejected = [
        FetchFailure(location=item.location, reason=item.reason) for item in selected.rejected
    ]
    result = collect_pages(selected.targets, failures=rejected, fetch=fetch, limit=limit)
    # 返した本文の場所だけを既読にする
    append_record(state_dir, session_id, [page.location for page in result.pages])
    return result


def build_server(env: Mapping[str, str], fetch: FetchUrlFn = fetch_url) -> MCPServer:
    """read_rules を登録した MCP サーバーを返す。"""
    server = MCPServer(SERVER_NAME)

    @server.tool(name="read_rules", meta={"anthropic/maxResultSizeChars": MAX_RESULT_CHARS})
    def read_rules_tool(
        locations: Annotated[
            list[str], Field(default_factory=list, description=LOCATIONS_DESCRIPTION)
        ],
        paths: Annotated[list[str], Field(default_factory=list, description=PATHS_DESCRIPTION)],
        session_id: Annotated[str | None, Field(default=None, description=SESSION_ID_DESCRIPTION)],
    ) -> str:
        """ルールの場所か、これから触るファイルのパスを受け、当たるルールの本文を返して既読にする。"""
        # 呼ばれるたびに索引と記録フォルダを求める（環境変数の変更を次の呼び出しで反映する）
        folder = state_dir(env)
        log_session = session_id if is_valid_session_id(session_id) else None
        loaded = load_indexes(env)
        for failure in loaded.failures:
            write_log(
                folder,
                component=Component.READ_RULES,
                operation=LogOperation.READ_INDEX,
                reason=failure.reason,
                session_id=log_session,
                path=failure.path,
            )
        try:
            result = read_rules(
                locations,
                paths,
                session_id,
                entries=loaded.entries,
                state_dir=folder,
                fetch=fetch,
            )
        except ToolArgumentError as exc:
            _log_failure(folder, LogOperation.UNEXPECTED, log_session, None, str(exc))
            raise ToolError(str(exc)) from exc
        except RecordWriteError as exc:
            _log_failure(folder, LogOperation.WRITE_RECORD, log_session, exc.path, exc.reason)
            raise ToolError(
                f"既読の記録に書けませんでした（本文は返していません）: {exc.path}: {exc.reason}"
            ) from exc
        except Exception as exc:
            _log_failure(folder, LogOperation.UNEXPECTED, log_session, None, describe(exc))
            raise ToolError(describe(exc)) from exc
        return render_result(result)

    return server


def _log_failure(
    folder: Path,
    operation: LogOperation,
    session_id: str | None,
    path: str | None,
    reason: str,
) -> None:
    """read_rules の失敗をログへ書く。"""
    write_log(
        folder,
        component=Component.READ_RULES,
        operation=operation,
        reason=reason,
        session_id=session_id,
        path=path,
    )
