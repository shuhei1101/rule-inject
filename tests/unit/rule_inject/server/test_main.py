"""server/__main__.py の単体テスト。"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from mcp import StdioServerParameters
from mcp.client import Client

PROJECT_ROOT = Path(__file__).resolve().parents[4]


async def _list_tool_names(params: StdioServerParameters) -> list[str]:
    """子プロセスのサーバーへ stdio で接続し、ツール名の一覧を返す。"""
    async with Client(params) as client:
        return [tool.name for tool in (await client.list_tools()).tools]


def test_main(hook_env: dict[str, str]) -> None:
    """子プロセスで起動して tools/list に答える（正常系）。"""
    # 準備
    env: dict[str, Any] = {**os.environ, **hook_env}
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "rule_inject.server"],
        env=env,
        cwd=PROJECT_ROOT,
    )
    # 実行
    names = asyncio.run(_list_tool_names(params))
    # 検証
    assert "read_rules" in names
