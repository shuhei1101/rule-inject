"""インターフェース定義『既読の記録の確認』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

MISSING_HASH = "sha256:" + "0" * 64


def _row(session: str, location: Path, method: str, tool: str, time: str) -> dict[str, str]:
    """既読の履歴の 1 行（JSON のオブジェクト）を作る。"""
    return {
        "time": time,
        "session_id": session,
        "method": method,
        "tool": tool,
        "location": str(location),
    }


def test_normal(
    state_dir: Path,
    session_id: str,
    record_server: Any,
    rule_file: Callable[..., Path],
    hashed: Callable[[Path], str],
    write_record: Callable[..., Path],
    write_history_rows: Callable[..., Path],
) -> None:
    """既読のルールごとに、今の本文との関係と読んだ方法を返す（正常系）。"""
    # 準備
    read_rule = rule_file("read.md", "# read\n")
    mcp_rule = rule_file("mcp.md", "# mcp\n")
    record = write_record([f"{read_rule}\t{hashed(read_rule)}", f"{mcp_rule}\t{hashed(mcp_rule)}"])
    history = write_history_rows(
        [
            _row(session_id, read_rule, "read", "Read", "2026-10-24T09:30:00Z"),
            "{broken json",
            _row(session_id, mcp_rule, "mcp", "mcp__docs__get_doc", "2026-10-24T09:31:00Z"),
            _row(session_id, mcp_rule, "mcp", "mcp__docs__get_doc", "2026-10-24T09:31:12Z"),
        ]
    )
    before = (record.read_bytes(), history.read_bytes())
    # 実行
    result = record_server.call("get_read_records", session_id=session_id, format="json")
    # 検証
    content = result.structured_content
    assert [(rule["location"], rule["state"]) for rule in content["rules"]] == [
        (str(read_rule), "current"),
        (str(mcp_rule), "current"),
    ]
    assert content["rules"][0]["reads"] == [
        {"method": "read", "tool": "Read", "last_time": "2026-10-24T09:30:00Z", "count": 1}
    ]
    assert content["rules"][1]["reads"] == [
        {
            "method": "mcp",
            "tool": "mcp__docs__get_doc",
            "last_time": "2026-10-24T09:31:12Z",
            "count": 2,
        }
    ]
    assert content["state_dir"] == str(state_dir)
    assert (record.read_bytes(), history.read_bytes()) == before


def test_normal_when_rule_changed(
    tmp_path: Path,
    session_id: str,
    record_server: Any,
    rule_file: Callable[..., Path],
    hashed: Callable[[Path], str],
    write_record: Callable[..., Path],
) -> None:
    """本文が変わったルールを `changed`、ファイルが無いルールを `missing` で返す（正常系）。"""
    # 準備
    changed = rule_file("changed.md", "# before\n")
    gone = tmp_path / "rules" / "gone.md"
    write_record([f"{changed}\t{hashed(changed)}", f"{gone}\t{MISSING_HASH}"])
    changed.write_text("# after\n", encoding="utf-8")
    # 実行
    result = record_server.call("get_read_records", session_id=session_id, format="json")
    # 検証
    assert [(rule["location"], rule["state"]) for rule in result.structured_content["rules"]] == [
        (str(changed), "changed"),
        (str(gone), "missing"),
    ]


def test_normal_when_session_omitted(
    record_server: Any,
    write_record: Callable[..., Path],
    write_guided: Callable[..., Path],
    write_history_rows: Callable[..., Path],
    set_age_days: Callable[[Path, int], Path],
) -> None:
    """既読の記録のあるセッションを最終更新の新しい順に返す（正常系）。"""
    # 準備
    newer = write_record([f"/r/a.md\t{MISSING_HASH}", f"/r/b.md\t{MISSING_HASH}"], name="newer")
    older = write_record([f"/r/a.md\t{MISSING_HASH}"], name="older")
    set_age_days(newer, 1)
    set_age_days(older, 3)
    write_guided(["/r/a.md"], name="newer")
    write_history_rows([], name="newer")
    # 実行
    result = record_server.call("get_read_records", format="json")
    # 検証
    content = result.structured_content
    assert [(item["session_id"], item["rule_count"]) for item in content["sessions"]] == [
        ("newer", 2),
        ("older", 1),
    ]
    assert all(item["updated_at"] for item in content["sessions"])
    assert content["session_id"] is None
    assert content["rules"] == []


def test_normal_when_more_rules(
    session_id: str,
    record_server: Any,
    write_record: Callable[..., Path],
) -> None:
    """`limit` を超えるルールは `next_cursor` で続きを取らせる（正常系）。"""
    # 準備
    write_record([f"/r/{name}.md\t{MISSING_HASH}" for name in ("a", "b", "c")])
    # 実行
    first = record_server.call("get_read_records", session_id=session_id, limit=2, format="json")
    second = record_server.call(
        "get_read_records",
        session_id=session_id,
        limit=2,
        cursor=first.structured_content["next_cursor"],
        format="json",
    )
    # 検証
    assert len(first.structured_content["rules"]) == 2
    assert first.structured_content["total"] == 3
    assert first.structured_content["next_cursor"] is not None
    assert [rule["location"] for rule in second.structured_content["rules"]] == ["/r/c.md"]
    assert second.structured_content["next_cursor"] is None


def test_error_when_session_id_invalid(
    record_server: Any,
    text_of: Callable[[CallToolResult], str],
) -> None:
    """記録ファイル名に使えない `session_id` をエラーにする（異常系）。"""
    # 実行
    result = record_server.call("get_read_records", session_id="../other", format="json")
    # 検証
    assert result.is_error is True
    assert "../other" in text_of(result)
