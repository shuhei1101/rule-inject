"""server/app.py の単体テスト。"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.client import Client
from mcp.server.mcpserver import MCPServer

from rule_inject.server.app import build_server


async def _list_tools(server: MCPServer) -> list[Any]:
    """サーバーに接続してツールの一覧を返す。"""
    async with Client(server) as client:
        return (await client.list_tools()).tools


async def _call_tool(server: MCPServer, name: str, arguments: dict[str, Any]) -> Any:
    """サーバーに接続してツールを呼び、応答を返す。"""
    async with Client(server) as client:
        return await client.call_tool(name, arguments)


def test_build_server() -> None:
    """read_rules が上限の指定つきで登録される（正常系）。"""
    # 準備
    server = build_server({})
    # 実行
    tools = asyncio.run(_list_tools(server))
    # 検証
    assert [tool.name for tool in tools] == ["read_rules"]
    assert tools[0].meta["anthropic/maxResultSizeChars"] == 40000
    properties = tools[0].input_schema["properties"]
    assert "paths" in properties["locations"]["description"]
    assert "locations" in properties["paths"]["description"]
    assert "フック" in properties["session_id"]["description"]


def test_build_server_when_error(hook_env: dict[str, str]) -> None:
    """引数が足りない呼び出しをエラーにする（正常系）。"""
    # 準備
    server = build_server(hook_env)
    # 実行
    result = asyncio.run(_call_tool(server, "read_rules", {"locations": ["/r/a.md"]}))
    # 検証
    assert result.is_error is True
    assert "session_id" in result.content[0].text
