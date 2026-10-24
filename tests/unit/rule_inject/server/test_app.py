"""server/app.py の単体テスト。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.client import Client
from mcp.server.mcpserver import MCPServer

from rule_inject.features.fetch.service import render_result
from rule_inject.features.fetch.types import ReadRulesResult, RulePage
from rule_inject.server.app import ToolArgumentError, build_server, read_rules
from rule_inject.shared.errors import RecordWriteError


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


def test_read_rules(
    state_dir: Path,
    log_folder: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """場所で引いて既読にする（正常系）。"""
    # 準備
    rule = rule_file("python.md", "# Python の規約\n")
    entries = [make_entry(str(rule))]
    # 実行
    result = read_rules(
        [str(rule)], [], session_id, entries=entries, state_dir=state_dir, log_dir=log_folder
    )
    # 検証
    assert result.pages == [RulePage(location=str(rule), body="# Python の規約\n")]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "read_rules"
    assert history[0]["tool"] == "mcp__plugin_rule-inject_rule-inject__read_rules"
    assert history[0]["location"] == str(rule)
    assert result.history_failures == []


def test_read_rules_when_rejected(
    state_dir: Path,
    log_folder: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """読まない場所を failures に載せ、既読にしない（正常系）。"""
    # 準備
    listed = rule_file("listed.md")
    unlisted = rule_file("unlisted.md")
    entries = [make_entry(str(listed))]
    # 実行
    result = read_rules(
        [str(unlisted), str(listed)],
        [],
        session_id,
        entries=entries,
        state_dir=state_dir,
        log_dir=log_folder,
    )
    # 検証
    assert len(result.failures) == 1
    assert "索引に載っていない場所" in result.failures[0].reason
    assert result.pages == [RulePage(location=str(listed), body="# 規約\n")]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(listed)]


def test_read_rules_when_deferred(
    state_dir: Path,
    log_folder: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """次に回した場所は既読にしない（正常系）。"""
    # 準備
    first = rule_file("a.md", "a" * 50)
    second = rule_file("b.md", "b" * 50)
    entries = [make_entry(str(first)), make_entry(str(second))]
    one_page_and_deferred = ReadRulesResult(
        pages=[RulePage(location=str(first), body="a" * 50)],
        deferred=[str(second)],
        failures=[],
    )
    limit = len(render_result(one_page_and_deferred))
    # 実行
    result = read_rules(
        [str(first), str(second)],
        [],
        session_id,
        entries=entries,
        state_dir=state_dir,
        log_dir=log_folder,
        limit=limit,
    )
    # 検証
    assert result.deferred == [str(second)]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(first)]
    history = read_history()
    assert len(history) == 1
    assert history[0]["location"] == str(first)


def test_read_rules_when_no_session_id(
    state_dir: Path,
    log_folder: Path,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
) -> None:
    """session_id が無ければ ToolArgumentError にする（異常系）。"""
    # 準備
    rule = rule_file()
    entries = [make_entry(str(rule))]
    # 実行・検証
    with pytest.raises(ToolArgumentError, match="session_id"):
        read_rules([str(rule)], [], None, entries=entries, state_dir=state_dir, log_dir=log_folder)


def test_read_rules_when_no_target(state_dir: Path, log_folder: Path, session_id: str) -> None:
    """引く対象が無ければ ToolArgumentError にする（異常系）。"""
    # 実行・検証
    with pytest.raises(ToolArgumentError, match="locations"):
        read_rules([], [], session_id, entries=[], state_dir=state_dir, log_dir=log_folder)


def test_read_rules_when_record_unwritable(
    state_dir: Path,
    log_folder: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """記録に書けなければ RecordWriteError にする（異常系）。"""
    # 準備
    rule = rule_file()
    entries = [make_entry(str(rule))]
    state_dir.mkdir()
    unwritable(state_dir, 0o555)
    # 実行・検証
    with pytest.raises(RecordWriteError):
        read_rules(
            [str(rule)], [], session_id, entries=entries, state_dir=state_dir, log_dir=log_folder
        )


def test_read_rules_when_history_unwritable(
    state_dir: Path,
    log_folder: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    read_lines: Callable[[Path], list[str]],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """履歴に書けなくても本文を返し、history_failures に載せる（正常系）。"""
    # 準備
    rule = rule_file("python.md", "# Python の規約\n")
    entries = [make_entry(str(rule))]
    (state_dir / f"{session_id}.history.jsonl").mkdir(parents=True)
    # 実行
    result = read_rules(
        [str(rule)], [], session_id, entries=entries, state_dir=state_dir, log_dir=log_folder
    )
    # 検証
    assert result.pages == [RulePage(location=str(rule), body="# Python の規約\n")]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]
    assert [failure.location for failure in result.history_failures] == [str(rule)]
    assert "IsADirectoryError" in result.history_failures[0].reason
    log = read_daily_log()
    assert len(log) == 1
    assert log[0]["operation"] == "write_history"
