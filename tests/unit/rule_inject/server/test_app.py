"""server/app.py の単体テスト。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

TOOL_NAMES = [
    "check_indexes",
    "delete_index_entry",
    "delete_read_records",
    "get_read_records",
    "get_server_status",
    "list_rules",
    "reload_settings",
    "restart_server",
    "search_rules",
    "update_server",
    "write_index_entry",
]
INJECTED_NAMES = {
    "env",
    "validator",
    "locks",
    "check_change",
    "scan_time_limit",
    "dev_docs_timeout",
    "control",
    "clone",
    "run_command",
}


@pytest.fixture
def clone_dir(tmp_path: Path) -> Path:
    """`version.ini` を置いたクローンの代わりのフォルダ。"""
    (tmp_path / "version.ini").write_text("v0.2.4\n", encoding="utf-8")
    return tmp_path


def test_build_server(clone_dir: Path) -> None:
    """11 のツールを依存の引数なしで登録する（正常系）。"""
    from rule_inject.server.app import build_server
    from rule_inject.server.control import ServerControl

    # 準備
    server = build_server({}, control=ServerControl(port=8783), clone=clone_dir)
    # 実行
    tools = asyncio.run(server.list_tools())
    # 検証
    schema_keys = {key for tool in tools for key in tool.input_schema.get("properties", {})}
    destructive = {
        tool.name for tool in tools if tool.annotations and tool.annotations.destructive_hint
    }
    assert sorted(tool.name for tool in tools) == TOOL_NAMES
    assert schema_keys.isdisjoint(INJECTED_NAMES)
    assert destructive == {
        "delete_index_entry",
        "delete_read_records",
        "restart_server",
        "update_server",
    }


def test_build_server_instructions(clone_dir: Path) -> None:
    """instructions を指定する（正常系）。"""
    from rule_inject.server.app import SERVER_INSTRUCTIONS, build_server
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=8783)
    # 実行
    server = build_server({}, control=control, clone=clone_dir)
    # 検証
    assert server.instructions == SERVER_INSTRUCTIONS
    assert len(SERVER_INSTRUCTIONS) <= 4096
    assert "Write" in SERVER_INSTRUCTIONS
    assert "空の内容" in SERVER_INSTRUCTIONS
    assert "Edit" in SERVER_INSTRUCTIONS


def test_build_server_when_restarting(clone_dir: Path) -> None:
    """再起動の途中は状態の確認だけを受け付ける（異常系）。"""
    from rule_inject.server.app import build_server
    from rule_inject.server.control import ServerControl

    # 準備
    control = ServerControl(port=8783)
    fake_server: Any = SimpleNamespace(should_exit=False)
    control.attach(fake_server)
    server = build_server({}, control=control, clone=clone_dir)

    async def scenario() -> Any:
        """再起動を始めてから状態の確認を呼ぶ。"""
        control.begin_restart()
        return await server.call_tool("get_server_status", {})

    async def refused() -> Any:
        """再起動の途中に一覧のツールを呼ぶ。"""
        return await server.call_tool("list_rules", {"project_dir": str(clone_dir)})

    # 実行
    status = asyncio.run(scenario())
    # 検証
    assert status.structured_content["restarting"] is True
    with pytest.raises(ToolError, match="再起動の途中"):
        asyncio.run(refused())
