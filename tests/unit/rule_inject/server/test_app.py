"""server/app.py の単体テスト。"""

from __future__ import annotations

import asyncio

TOOL_NAMES = [
    "check_indexes",
    "delete_index_entry",
    "list_rules",
    "search_rules",
    "write_index_entry",
]
INJECTED_NAMES = {"env", "validator", "locks", "check_change"}


def test_build_server() -> None:
    """5 つのツールを依存の引数なしで登録する（正常系）。"""
    from rule_inject.server.app import build_server

    # 準備
    server = build_server({})
    # 実行
    tools = asyncio.run(server.list_tools())
    # 検証
    schema_keys = {key for tool in tools for key in tool.input_schema.get("properties", {})}
    destructive = {
        tool.name for tool in tools if tool.annotations and tool.annotations.destructive_hint
    }
    assert sorted(tool.name for tool in tools) == TOOL_NAMES
    assert schema_keys.isdisjoint(INJECTED_NAMES)
    assert destructive == {"delete_index_entry"}
