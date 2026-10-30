"""dev-docs の `search_docs` で、使われているタグを引くクライアント。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent

from rule_inject.shared.errors import describe

# 使われているタグを引く dev-docs のツール
SEARCH_DOCS_TOOL = "search_docs"
# `search_docs` に渡す固定の引数（これに `cwd` を加える）
TAG_GROUP_ARGUMENTS = {"source": "*", "group_by": "tags", "format": "json"}
# 応答を読めないときの理由に載せる、応答の文字列の字数の上限
UNREADABLE_EXCERPT_CHARS = 200


@dataclass(frozen=True, slots=True)
class UsedTags:
    """`fetch_used_tags` の結果。引けたタグか、引けなかった理由のどちらかを持つ。"""

    # `groups[].value` の並び。`reason` があるときは空
    tags: tuple[str, ...]
    # タグを引けなかった理由（接続先の URL を含む）。引けたときは None
    reason: str | None


@asynccontextmanager
async def _open_session(url: str) -> AsyncIterator[ClientSession]:
    """接続先へ Streamable HTTP で接続し、初期化したセッションを渡す。抜けるときにセッションとストリームを閉じる。"""
    async with streamable_http_client(url) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        yield session


def _skipped(reason: str) -> UsedTags:
    """タグを引けなかった結果を作る。"""
    return UsedTags(tags=(), reason=reason)


def _parse_tags(url: str, project_dir: str, result: Any) -> UsedTags:
    """`search_docs` の結果から、使われているタグか引けなかった理由を作る。"""
    text = (
        "".join(item.text for item in result.content if isinstance(item, TextContent))
        if isinstance(result, CallToolResult)
        else ""
    )
    # ツールがエラーを返したときは、その文面を理由にする
    if isinstance(result, CallToolResult) and result.is_error:
        return _skipped(f"{url} が {SEARCH_DOCS_TOOL} のエラーを返した: {text}")
    try:
        body = json.loads(text)
    except ValueError:
        body = None
    total = body.get("total_count") if isinstance(body, dict) else None
    # `total_count` が整数でない応答は読めない
    if not isinstance(total, int) or isinstance(total, bool):
        return _skipped(f"{url} の応答を読めない: {text[:UNREADABLE_EXCERPT_CHARS]}")
    # 読める文書が 0 件のときは `groups` が返らず、全てのパターンが使われていないと誤って報告してしまう
    if total == 0:
        return _skipped(f"{url} から {project_dir} で読める文書が 0 件だった")
    groups = body.get("groups", [])
    return UsedTags(
        tags=tuple(
            group["value"]
            for group in groups
            if isinstance(group, dict) and isinstance(group.get("value"), str)
        ),
        reason=None,
    )


async def _search_tags(
    url: str,
    project_dir: str,
    open_session: Callable[[str], AbstractAsyncContextManager[ClientSession]],
) -> UsedTags:
    """セッションを開いて `search_docs` を呼び、接続・通信に失敗したときは理由を返す。"""
    result: Any = None
    failure: str | None = None
    try:
        async with open_session(url) as session:
            result = await session.call_tool(
                SEARCH_DOCS_TOOL, {**TAG_GROUP_ARGUMENTS, "cwd": project_dir}
            )
    except* (httpx2.HTTPError, OSError, MCPError) as group:
        # anyio の TaskGroup が包んだ例外の中のものも含めて、接続・通信の失敗にする
        failure = ", ".join(describe(exc) for exc in group.exceptions)
    if failure is not None:
        return _skipped(f"{url} に接続できない: {failure}")
    return _parse_tags(url, project_dir, result)


async def fetch_used_tags(
    url: str,
    project_dir: str,
    *,
    timeout: float,  # noqa: ASYNC109 - 待ち時間の上限は呼び出し元が決める値として受ける
    open_session: Callable[[str], AbstractAsyncContextManager[ClientSession]] = _open_session,
) -> UsedTags:
    """dev-docs の `search_docs` を `group_by: tags` で 1 回呼び、使われているタグを返す。届かないときは例外にせず理由を返す。"""
    try:
        async with asyncio.timeout(timeout):
            return await _search_tags(url, project_dir, open_session)
    except TimeoutError:
        return _skipped(f"{url} の応答を {timeout:g} 秒待ったが返らなかった")
