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
    """`version.ini` を配置したクローンの代わりのフォルダ。"""
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
        "update_server",
        "write_index_entry",
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
    assert "check_indexes" in SERVER_INSTRUCTIONS
    assert "delete_index_entry" in SERVER_INSTRUCTIONS
    assert "delete_read_records" in SERVER_INSTRUCTIONS
    assert "get_read_records" in SERVER_INSTRUCTIONS
    assert "get_server_status" in SERVER_INSTRUCTIONS
    assert "list_rules" in SERVER_INSTRUCTIONS
    assert "reload_settings" in SERVER_INSTRUCTIONS
    assert "restart_server" in SERVER_INSTRUCTIONS
    assert "search_rules" in SERVER_INSTRUCTIONS
    assert "update_server" in SERVER_INSTRUCTIONS
    assert "write_index_entry" in SERVER_INSTRUCTIONS
    assert "Read" in SERVER_INSTRUCTIONS
    assert "grep" in SERVER_INSTRUCTIONS


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


def test_build_server_session_env(clone_dir: Path) -> None:
    """設定を使用するツールだけが `session_env` を引数に持つ（正常系）。"""
    from rule_inject.server.app import build_server
    from rule_inject.server.control import ServerControl

    # 準備
    server = build_server({}, control=ServerControl(port=8783), clone=clone_dir)
    # 実行
    tools = asyncio.run(server.list_tools())
    # 検証
    with_session_env = sorted(
        tool.name for tool in tools if "session_env" in tool.input_schema.get("properties", {})
    )
    required = {key for tool in tools for key in tool.input_schema.get("required", [])}
    assert with_session_env == [
        "check_indexes",
        "delete_index_entry",
        "delete_read_records",
        "get_read_records",
        "list_rules",
        "search_rules",
        "write_index_entry",
    ]
    assert "session_env" not in required


def test_build_server_when_session_env(
    clone_dir: Path,
    tmp_path: Path,
    make_settings: Any,
    make_index: Any,
) -> None:
    """`session_env` の設定ファイルで照合する（正常系）。"""
    from rule_inject.server.app import build_server
    from rule_inject.server.control import ServerControl

    # 準備
    index = make_index("rules:\n  - rule: /r/a.md\n    paths: ['**/*.py']\n", name="session.yaml")
    server_config = make_settings("global:\n  indexes: []\n", name="server.yaml")
    session_config = make_settings(f"global:\n  indexes:\n    - {index}\n", name="session.yaml")
    server = build_server(
        {"RULE_INJECT_CONFIG": str(server_config)},
        control=ServerControl(port=8783),
        clone=clone_dir,
    )
    arguments = {
        "project_dir": str(tmp_path),
        "format": "json",
        "session_env": {"RULE_INJECT_CONFIG": str(session_config)},
    }
    # 実行
    result: Any = asyncio.run(server.call_tool("list_rules", arguments))
    # 検証
    assert result.structured_content["config_path"] == str(session_config)
    assert result.structured_content["indexes"] == [str(index)]


def test_session_environment() -> None:
    """3 つの名前を除いて `session_env` を重ねる（正常系）。"""
    from rule_inject.server.app import _session_environment

    # 準備
    env = {
        "RULE_INJECT_CONFIG": "/server/settings.yaml",
        "XDG_CONFIG_HOME": "/server/config",
        "XDG_STATE_HOME": "/server/state",
        "HOME": "/home/user",
    }
    session_env = {"XDG_CONFIG_HOME": "/session/config", "RULE_ROOT": "/rules"}
    # 実行
    result = _session_environment(env, session_env)
    # 検証
    assert dict(result) == {
        "HOME": "/home/user",
        "XDG_CONFIG_HOME": "/session/config",
        "RULE_ROOT": "/rules",
    }


def test_session_environment_when_absent() -> None:
    """`session_env` が無ければサーバーの環境変数を使用する（正常系）。"""
    from rule_inject.server.app import _session_environment

    # 準備
    env = {"RULE_INJECT_CONFIG": "/server/settings.yaml", "HOME": "/home/user"}
    # 実行
    result = _session_environment(env, None)
    # 検証
    assert dict(result) == {"RULE_INJECT_CONFIG": "/server/settings.yaml", "HOME": "/home/user"}
