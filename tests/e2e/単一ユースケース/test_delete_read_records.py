"""単一ユースケース「既読の記録を削除する」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

SESSION = "2f9c1b7e-0d54-4b7a-9d4f-5c3a1e2b7f10"
OTHER_SESSION = "other-session"
HASH = "sha256:" + "0" * 64


def test_normal(
    state_dir: Path,
    serve: Callable[..., Any],
) -> None:
    """そのセッションの既読の記録と案内済みの記録だけを削除し、既読だったルールの場所を受け取る（正常シナリオ）。"""
    # 準備
    state_dir.mkdir(parents=True)
    (state_dir / f"{SESSION}.txt").write_text(
        f"/r/a.md\t{HASH}\n/r/b.md\t{HASH}\n", encoding="utf-8"
    )
    (state_dir / f"{SESSION}.guided.txt").write_text("/r/a.md\n", encoding="utf-8")
    history = state_dir / f"{SESSION}.history.jsonl"
    history.write_text("{}\n", encoding="utf-8")
    other = state_dir / f"{OTHER_SESSION}.txt"
    other.write_text(f"/r/c.md\t{HASH}\n", encoding="utf-8")
    server = serve()
    # 実行
    result = server.call("delete_read_records", session_id=SESSION)
    # 検証
    assert result.structured_content["locations"] == ["/r/a.md", "/r/b.md"]
    assert not (state_dir / f"{SESSION}.txt").exists()
    assert not (state_dir / f"{SESSION}.guided.txt").exists()
    assert history.exists()
    assert other.exists()


def test_normal_when_no_record(
    serve: Callable[..., Any],
) -> None:
    """記録の無いセッションは、エラーにならず未読に戻したルールが空になる（正常シナリオ）。"""
    # 準備
    server = serve()
    # 実行
    result = server.call("delete_read_records", session_id=SESSION)
    # 検証
    assert result.is_error is False
    assert result.structured_content["locations"] == []


def test_error_when_session_id_invalid(
    state_dir: Path,
    serve: Callable[..., Any],
    tool_text: Callable[[CallToolResult], str],
) -> None:
    """記録ファイル名に使えないセッションを渡すと、形式が誤っている旨のエラーを受け取り、何も削除されない（異常シナリオ）。"""
    # 準備
    state_dir.mkdir(parents=True)
    record = state_dir / f"{SESSION}.txt"
    record.write_text(f"/r/a.md\t{HASH}\n", encoding="utf-8")
    server = serve()
    # 実行
    result = server.call("delete_read_records", session_id="../other")
    # 検証
    assert result.is_error is True
    assert "../other" in tool_text(result)
    assert "形式" in tool_text(result)
    assert sorted(path.name for path in state_dir.iterdir()) == [record.name]
