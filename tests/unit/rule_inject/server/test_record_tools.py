"""server/record_tools.py の単体テスト。"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

HASH_A = "sha256:aaaa"
HASH_TEST = "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


@pytest.fixture
def record_env(
    server_env: Callable[..., dict[str, str]],
    state_dir: Path,
) -> dict[str, str]:
    """`global.state_dir` でテストの記録フォルダを指す設定ファイルを指す環境変数。"""
    return server_env(f"global:\n  state_dir: {state_dir}\n")


@pytest.fixture
def write_session_record(state_dir: Path) -> Callable[..., Path]:
    """指定のセッションの既読の記録を、最終更新を決めて置く factory。"""

    def _write(target_session_id: str, lines: Sequence[str], modified: int) -> Path:
        """target_session_id の記録ファイルに lines を書き、最終更新を modified（UNIX 時刻の秒）にする。"""
        path = state_dir / f"{target_session_id}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        os.utime(path, (modified, modified))
        return path

    return _write


def _at(second: int) -> Callable[[], datetime]:
    """2026-10-24 09:30 台の固定した時刻（秒を second にした UTC）を返す関数を作る。"""
    return lambda: datetime(2026, 10, 24, 9, 30, second, tzinfo=UTC)


def test_get_read_records(
    tmp_path: Path,
    state_dir: Path,
    session_id: str,
    record_env: dict[str, str],
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """既読のルールごとに状態と読み方のまとめを返す（正常系）。"""
    from rule_inject.features.record import ReadMethod, append_history
    from rule_inject.server.record_tools import get_read_records

    # 準備
    same = tmp_path / "rules" / "same.md"
    same.parent.mkdir()
    same.write_text("test", encoding="utf-8")
    changed = tmp_path / "rules" / "changed.md"
    changed.write_text("after", encoding="utf-8")
    write_record([f"{same}\t{HASH_TEST}", f"{changed}\t{HASH_TEST}"])
    append_history(
        state_dir, session_id, [str(same)], method=ReadMethod.READ, tool="Read", now=_at(0)
    )
    append_history(
        state_dir,
        session_id,
        [str(changed)],
        method=ReadMethod.MCP,
        tool="mcp__docs__get_doc",
        now=_at(5),
    )
    append_history(
        state_dir,
        session_id,
        [str(changed)],
        method=ReadMethod.MCP,
        tool="mcp__docs__get_doc",
        now=_at(12),
    )
    # 実行
    result = get_read_records(session_id=session_id, format="json", env=record_env)
    # 検証
    content = result.structured_content
    assert content["state_dir"] == str(state_dir)
    assert [(rule["location"], rule["state"]) for rule in content["rules"]] == [
        (str(same), "current"),
        (str(changed), "changed"),
    ]
    assert content["rules"][0]["reads"] == [
        {"method": "read", "tool": "Read", "last_time": "2026-10-24T09:30:00Z", "count": 1}
    ]
    assert content["rules"][1]["reads"] == [
        {
            "method": "mcp",
            "tool": "mcp__docs__get_doc",
            "last_time": "2026-10-24T09:30:12Z",
            "count": 2,
        }
    ]


def test_get_read_records_when_sessions(
    record_env: dict[str, str],
    write_session_record: Callable[..., Path],
) -> None:
    """セッションを省くとセッションの一覧を返す（正常系）。"""
    from rule_inject.server.record_tools import get_read_records

    # 準備
    write_session_record("old-session", [f"/r/a.md\t{HASH_A}"], 1_700_000_000)
    write_session_record("new-session", [f"/r/a.md\t{HASH_A}", f"/r/b.md\t{HASH_A}"], 1_800_000_000)
    # 実行
    result = get_read_records(format="json", env=record_env)
    # 検証
    content = result.structured_content
    assert [(item["session_id"], item["rule_count"]) for item in content["sessions"]] == [
        ("new-session", 2),
        ("old-session", 1),
    ]
    assert content["session_id"] is None
    assert content["rules"] == []


def test_get_read_records_when_invalid_session(record_env: dict[str, str]) -> None:
    """形式の誤ったセッションを断る（異常系）。"""
    from rule_inject.server.record_tools import get_read_records

    # 実行・検証
    with pytest.raises(ToolError, match=re.escape("../x")):
        get_read_records(session_id="../x", format="json", env=record_env)


def test_delete_read_records(
    state_dir: Path,
    session_id: str,
    record_env: dict[str, str],
    write_record: Callable[[Sequence[str]], Path],
    write_guided: Callable[[Sequence[str]], Path],
    write_session_record: Callable[..., Path],
) -> None:
    """既読の記録と案内済みの記録を削除し、既読だった場所を返す（正常系）。"""
    from rule_inject.features.record import ReadMethod, append_history
    from rule_inject.server.record_tools import delete_read_records

    # 準備
    write_record([f"/r/a.md\t{HASH_A}", f"/r/b.md\t{HASH_A}"])
    write_guided(["/r/a.md"])
    append_history(
        state_dir, session_id, ["/r/a.md", "/r/b.md"], method=ReadMethod.READ, tool="Read"
    )
    other = write_session_record("other-session", [f"/r/c.md\t{HASH_A}"], 1_700_000_000)
    # 実行
    result = delete_read_records(session_id=session_id, env=record_env)
    # 検証
    assert result.structured_content["locations"] == ["/r/a.md", "/r/b.md"]
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.guided.txt").exists()
    assert (state_dir / f"{session_id}.history.jsonl").exists()
    assert other.exists()


def test_delete_read_records_when_missing(session_id: str, record_env: dict[str, str]) -> None:
    """記録の無いセッションは空の一覧を返す（正常系）。"""
    from rule_inject.server.record_tools import delete_read_records

    # 実行
    result = delete_read_records(session_id=session_id, env=record_env)
    # 検証
    assert result.is_error is False
    assert result.structured_content["success"] is True
    assert result.structured_content["locations"] == []


def test_delete_read_records_when_invalid_session(
    state_dir: Path,
    session_id: str,
    record_env: dict[str, str],
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """形式の誤ったセッションを断り、何も削除しない（異常系）。"""
    from rule_inject.server.record_tools import delete_read_records

    # 準備
    write_record([f"/r/a.md\t{HASH_A}"])
    # 実行・検証
    with pytest.raises(ToolError, match=re.escape("../other")):
        delete_read_records(session_id="../other", env=record_env)
    assert sorted(path.name for path in state_dir.iterdir()) == [f"{session_id}.txt"]
