"""単一ユースケース「既読の記録を確認する」の E2E テスト。"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

SESSION = "2f9c1b7e-0d54-4b7a-9d4f-5c3a1e2b7f10"
MCP_TOOL = "mcp__docs__get_doc"


def _hash(path: Path) -> str:
    """ルールの本文の SHA-256 を、既読の記録の書式（`sha256:{16 進数}`）で返す。"""
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _history_row(location: Path, method: str, tool: str, time: str) -> str:
    """既読の履歴の 1 行（JSON）を作る。"""
    return json.dumps(
        {
            "time": time,
            "session_id": SESSION,
            "method": method,
            "tool": tool,
            "location": str(location),
        }
    )


def test_normal(
    state_dir: Path,
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """既読のルールごとに、今の本文との関係と読んだ方法を受け取り、記録を書き換えない（正常シナリオ）。"""
    # 準備
    read_rule = make_rule("read.md", "# read\n")
    mcp_rule = make_rule("mcp.md", "# mcp\n")
    state_dir.mkdir(parents=True)
    record = state_dir / f"{SESSION}.txt"
    record.write_text(
        f"{read_rule}\t{_hash(read_rule)}\n{mcp_rule}\t{_hash(mcp_rule)}\n", encoding="utf-8"
    )
    history = state_dir / f"{SESSION}.history.jsonl"
    history.write_text(
        _history_row(read_rule, "read", "Read", "2026-10-24T09:30:00Z")
        + "\n"
        + _history_row(mcp_rule, "mcp", MCP_TOOL, "2026-10-24T09:31:00Z")
        + "\n",
        encoding="utf-8",
    )
    before = (record.read_bytes(), history.read_bytes())
    server = serve()
    # 実行
    result = server.call("get_read_records", session_id=SESSION, format="json")
    # 検証
    rules = {rule["location"]: rule for rule in result.structured_content["rules"]}
    assert set(rules) == {str(read_rule), str(mcp_rule)}
    assert {rule["state"] for rule in rules.values()} == {"current"}
    assert rules[str(read_rule)]["reads"] == [
        {"method": "read", "tool": "Read", "last_time": "2026-10-24T09:30:00Z", "count": 1}
    ]
    assert rules[str(mcp_rule)]["reads"] == [
        {"method": "mcp", "tool": MCP_TOOL, "last_time": "2026-10-24T09:31:00Z", "count": 1}
    ]
    assert (record.read_bytes(), history.read_bytes()) == before


def test_normal_when_rule_changed(
    state_dir: Path,
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """既読にした後に本文が変わったルールが、今の本文と違うと分かる（正常シナリオ）。"""
    # 準備
    rule = make_rule("changed.md", "# before\n")
    state_dir.mkdir(parents=True)
    (state_dir / f"{SESSION}.txt").write_text(f"{rule}\t{_hash(rule)}\n", encoding="utf-8")
    (state_dir / f"{SESSION}.history.jsonl").write_text(
        _history_row(rule, "read", "Read", "2026-10-24T09:30:00Z") + "\n", encoding="utf-8"
    )
    rule.write_text("# after\n", encoding="utf-8")
    server = serve()
    # 実行
    result = server.call("get_read_records", session_id=SESSION, format="json")
    # 検証
    assert [(item["location"], item["state"]) for item in result.structured_content["rules"]] == [
        (str(rule), "changed")
    ]


def test_normal_when_session_omitted(
    state_dir: Path,
    serve: Callable[..., Any],
) -> None:
    """セッションを指さないと、既読の記録のあるセッションを最終更新の新しい順に受け取る（正常シナリオ）。"""
    # 準備
    state_dir.mkdir(parents=True)
    hash_value = "sha256:" + "0" * 64
    for name, age in (("older-session", 3_000_000), ("newer-session", 1_000_000)):
        path = state_dir / f"{name}.txt"
        path.write_text(f"/r/a.md\t{hash_value}\n", encoding="utf-8")
        modified = 1_800_000_000 - age
        os.utime(path, (modified, modified))
    server = serve()
    # 実行
    result = server.call("get_read_records", format="json")
    # 検証
    content = result.structured_content
    assert [item["session_id"] for item in content["sessions"]] == [
        "newer-session",
        "older-session",
    ]
    assert all(item["updated_at"] for item in content["sessions"])
    assert content["rules"] == []


def test_error_when_session_id_invalid(
    state_dir: Path,
    serve: Callable[..., Any],
    tool_text: Callable[[CallToolResult], str],
) -> None:
    """記録ファイル名に使えないセッションを渡すと、形式が誤っている旨のエラーを受け取る（異常シナリオ）。"""
    # 準備
    server = serve()
    # 実行
    result = server.call("get_read_records", session_id="../other", format="json")
    # 検証
    assert result.is_error is True
    assert "../other" in tool_text(result)
    assert "形式" in tool_text(result)
