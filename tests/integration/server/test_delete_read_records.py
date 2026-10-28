"""インターフェース定義『既読の記録の削除』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

HASH = "sha256:" + "0" * 64


def test_normal(
    state_dir: Path,
    session_id: str,
    record_server: Any,
    write_record: Callable[..., Path],
    write_guided: Callable[..., Path],
    write_history: Callable[..., Path],
) -> None:
    """既読の記録と案内済みの記録を削除し、既読だったルールの場所を返す（正常系）。"""
    # 準備
    write_record([f"/r/a.md\t{HASH}", f"/r/b.md\t{HASH}"])
    write_guided(["/r/a.md"])
    history = write_history()
    other = write_record([f"/r/c.md\t{HASH}"], name="other-session")
    # 実行
    result = record_server.call("delete_read_records", session_id=session_id)
    # 検証
    assert result.structured_content["locations"] == ["/r/a.md", "/r/b.md"]
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.guided.txt").exists()
    assert history.exists()
    assert other.exists()


def test_normal_when_no_record(session_id: str, record_server: Any) -> None:
    """既読の記録の無いセッションは、何も削除せず空の一覧を返す（正常系）。"""
    # 実行
    result = record_server.call("delete_read_records", session_id=session_id)
    # 検証
    assert result.is_error is False
    assert result.structured_content["success"] is True
    assert result.structured_content["locations"] == []


def test_error_when_session_id_invalid(
    state_dir: Path,
    session_id: str,
    record_server: Any,
    write_record: Callable[..., Path],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """記録ファイル名に使えない `session_id` をエラーにし、何も削除しない（異常系）。"""
    # 準備
    write_record([f"/r/a.md\t{HASH}"])
    # 実行
    result = record_server.call("delete_read_records", session_id="../other")
    # 検証
    assert result.is_error is True
    assert "../other" in text_of(result)
    assert sorted(path.name for path in state_dir.iterdir()) == [f"{session_id}.txt"]
