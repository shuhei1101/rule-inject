"""features/record/service.py の単体テスト。"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.record import service
from rule_inject.features.record.service import (
    append_history,
    append_record,
    delete_record,
    is_valid_session_id,
    read_record,
    record_exists,
)
from rule_inject.features.record.types import ReadMethod
from rule_inject.shared.errors import (
    HistoryWriteError,
    RecordDeleteError,
    RecordReadError,
    RecordWriteError,
)


def test_is_valid_session_id(session_id: str) -> None:
    """UUID を許す（正常系）。"""
    # 実行
    result = is_valid_session_id(session_id)
    # 検証
    assert result is True


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("../x", id="traversal"),
        pytest.param("", id="empty"),
        pytest.param("a" * 129, id="too_long"),
        pytest.param(None, id="none"),
    ],
)
def test_is_valid_session_id_when_invalid(value: object) -> None:
    """形が外れた値を拒む（正常系）。"""
    # 実行
    result = is_valid_session_id(value)
    # 検証
    assert result is False


def test_read_record(
    state_dir: Path,
    session_id: str,
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """行を集合で返す（正常系）。"""
    # 準備
    write_record(["/r/a.md", "/r/a.md", "/r/b.md"])
    # 実行
    result = read_record(state_dir, session_id)
    # 検証
    assert result == frozenset({"/r/a.md", "/r/b.md"})


def test_read_record_when_missing(state_dir: Path, session_id: str) -> None:
    """ファイルが無ければ空を返す（正常系）。"""
    # 実行
    result = read_record(state_dir, session_id)
    # 検証
    assert result == frozenset()


def test_read_record_when_unreadable(
    state_dir: Path,
    session_id: str,
    write_record: Callable[[Sequence[str]], Path],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """読めない記録ファイルを RecordReadError にする（異常系）。"""
    # 準備
    record_file = unwritable(write_record(["/r/a.md"]), 0o000)
    # 実行・検証
    with pytest.raises(RecordReadError) as excinfo:
        read_record(state_dir, session_id)
    assert excinfo.value.path == str(record_file)


def test_append_record(
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """フォルダを作って追記する（正常系）。"""
    # 実行
    append_record(state_dir, session_id, ["/r/a.md", "/r/b.md"])
    append_record(state_dir, session_id, ["/r/c.md", "/r/d.md"])
    # 検証
    assert read_lines(state_dir / f"{session_id}.txt") == [
        "/r/a.md",
        "/r/b.md",
        "/r/c.md",
        "/r/d.md",
    ]


def test_append_record_when_empty(state_dir: Path, session_id: str) -> None:
    """空なら書かない（正常系）。"""
    # 実行
    append_record(state_dir, session_id, [])
    # 検証
    assert not state_dir.exists()


def test_append_record_when_unwritable(
    state_dir: Path,
    session_id: str,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """追記できないとき RecordWriteError にする（異常系）。"""
    # 準備
    state_dir.mkdir()
    unwritable(state_dir, 0o555)
    # 実行・検証
    with pytest.raises(RecordWriteError) as excinfo:
        append_record(state_dir, session_id, ["/r/a.md"])
    assert excinfo.value.path in {str(state_dir), str(state_dir / f"{session_id}.txt")}


def test_delete_record(
    state_dir: Path,
    session_id: str,
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """対象のセッションだけを消す（正常系）。"""
    # 準備
    target = write_record(["/r/a.md"])
    other = state_dir / "other-session.txt"
    other.write_text("/r/b.md\n", encoding="utf-8")
    # 実行
    delete_record(state_dir, session_id)
    # 検証
    assert not target.exists()
    assert other.exists()


def test_delete_record_when_missing(state_dir: Path, session_id: str) -> None:
    """記録ファイルが無ければ何もしない（正常系）。"""
    # 実行
    delete_record(state_dir, session_id)
    # 検証
    assert not state_dir.exists()


def test_delete_record_when_undeletable(
    state_dir: Path,
    session_id: str,
    write_record: Callable[[Sequence[str]], Path],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """消せない記録ファイルを RecordDeleteError にする（異常系）。"""
    # 準備
    write_record(["/r/a.md"])
    unwritable(state_dir, 0o555)
    # 実行・検証
    with pytest.raises(RecordDeleteError):
        delete_record(state_dir, session_id)


def test_record_exists(
    state_dir: Path,
    session_id: str,
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """記録ファイルの有無を返す（正常系）。"""
    # 準備
    write_record(["/r/a.md"])
    # 実行
    with_record = record_exists(state_dir, session_id)
    without_record = record_exists(state_dir, "other-session")
    # 検証
    assert with_record is True
    assert without_record is False


def test_sweep_records(
    state_dir: Path,
    session_id: str,
    now: Callable[[], float],
    write_aged_record: Callable[..., Path],
) -> None:
    """保持期間を過ぎた記録ファイルだけを消す（正常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31, base=now())
    within = write_aged_record("within-session", 29, base=now())
    # 実行
    result = service.sweep_records(state_dir, session_id, now=now, retention_days=30)
    # 検証
    assert not expired.exists()
    assert within.exists()
    assert result == ()


def test_sweep_records_when_kept_session(
    state_dir: Path,
    session_id: str,
    now: Callable[[], float],
    write_aged_record: Callable[..., Path],
) -> None:
    """始まったセッションの記録は消さない（正常系）。"""
    # 準備
    kept = write_aged_record(session_id, 31, base=now())
    # 実行
    service.sweep_records(state_dir, session_id, now=now, retention_days=30)
    # 検証
    assert kept.exists()


def test_sweep_records_when_not_record(
    tmp_path: Path,
    state_dir: Path,
    session_id: str,
    now: Callable[[], float],
) -> None:
    """記録ファイルでないものは消さない（正常系）。"""
    # 準備
    state_dir.mkdir()
    # 固定した now の 31 日前
    old = 1_797_321_600.0
    log_file = state_dir / "rule-inject.log"
    log_file.write_text("{}\n", encoding="utf-8")
    invalid_name = state_dir / "a b.txt"
    invalid_name.write_text("/r/a.md\n", encoding="utf-8")
    folder = state_dir / "folder.txt"
    folder.mkdir()
    link_target = tmp_path / "link-target.txt"
    link_target.write_text("/r/a.md\n", encoding="utf-8")
    link = state_dir / "link.txt"
    link.symlink_to(link_target)
    # 名前を除いて、消す対象の全ての条件を満たすよう最終更新を戻す
    for path in (log_file, invalid_name, folder, link_target):
        os.utime(path, (old, old))
    # 実行
    service.sweep_records(state_dir, session_id, now=now, retention_days=30)
    # 検証
    assert log_file.exists()
    assert invalid_name.exists()
    assert folder.is_dir()
    assert link.is_symlink()
    assert link_target.exists()


def test_sweep_records_when_missing(state_dir: Path, session_id: str) -> None:
    """記録フォルダが無ければ何もしない（正常系）。"""
    # 実行
    result = service.sweep_records(state_dir, session_id, retention_days=30)
    # 検証
    assert result == ()
    assert not state_dir.exists()


def test_sweep_records_when_undeletable(
    state_dir: Path,
    session_id: str,
    now: Callable[[], float],
    write_aged_record: Callable[..., Path],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """消せない記録ファイルを返す（異常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31, base=now())
    unwritable(state_dir, 0o555)
    # 実行
    result = service.sweep_records(state_dir, session_id, now=now, retention_days=30)
    # 検証
    assert len(result) == 1
    assert isinstance(result[0], RecordDeleteError)
    assert result[0].path == str(expired)
    assert expired.exists()


def test_sweep_records_when_guided(
    state_dir: Path,
    session_id: str,
    now: Callable[[], float],
    write_aged_record: Callable[..., Path],
) -> None:
    """保持期間を過ぎた案内済みの記録ファイルも消す（正常系）。"""
    # 準備
    suffix = ".guided.txt"
    expired = write_aged_record("expired-session", 31, base=now(), suffix=suffix)
    within = write_aged_record("within-session", 29, base=now(), suffix=suffix)
    kept = write_aged_record(session_id, 31, base=now(), suffix=suffix)
    invalid_name = write_aged_record("a b", 31, base=now(), suffix=suffix)
    # 実行
    result = service.sweep_records(state_dir, session_id, now=now, retention_days=30)
    # 検証
    assert not expired.exists()
    assert within.exists()
    assert kept.exists()
    assert invalid_name.exists()
    assert result == ()


def test_sweep_records_when_history(
    state_dir: Path,
    session_id: str,
    now: Callable[[], float],
    write_aged_record: Callable[..., Path],
) -> None:
    """保持期間を過ぎた既読の履歴ファイルも消す（正常系）。"""
    # 準備
    suffix = ".history.jsonl"
    expired = write_aged_record("expired-session", 31, base=now(), suffix=suffix)
    within = write_aged_record("within-session", 29, base=now(), suffix=suffix)
    kept = write_aged_record(session_id, 31, base=now(), suffix=suffix)
    invalid_name = write_aged_record("a b", 31, base=now(), suffix=suffix)
    # 実行
    result = service.sweep_records(state_dir, session_id, now=now, retention_days=30)
    # 検証
    assert not expired.exists()
    assert within.exists()
    assert kept.exists()
    assert invalid_name.exists()
    assert result == ()


def test_read_guided(
    state_dir: Path,
    session_id: str,
    write_record: Callable[[Sequence[str]], Path],
    write_guided: Callable[[Sequence[str]], Path],
) -> None:
    """案内済みの記録を集合で返す（正常系）。"""
    # 準備
    write_record(["/r/a.md"])
    write_guided(["/r/b.md", "/r/b.md"])
    # 実行
    result = service.read_guided(state_dir, session_id)
    # 検証
    assert result == frozenset({"/r/b.md"})


def test_read_guided_when_missing(state_dir: Path, session_id: str) -> None:
    """ファイルが無ければ空を返す（正常系）。"""
    # 実行
    result = service.read_guided(state_dir, session_id)
    # 検証
    assert result == frozenset()


def test_read_guided_when_unreadable(
    state_dir: Path,
    session_id: str,
    write_guided: Callable[[Sequence[str]], Path],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """読めない案内済みの記録ファイルを RecordReadError にする（異常系）。"""
    # 準備
    guided_file = unwritable(write_guided(["/r/b.md"]), 0o000)
    # 実行・検証
    with pytest.raises(RecordReadError) as excinfo:
        service.read_guided(state_dir, session_id)
    assert excinfo.value.path == str(guided_file)


def test_append_guided(
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """案内済みの記録ファイルへ追記する（正常系）。"""
    # 実行
    service.append_guided(state_dir, session_id, ["/r/a.md", "/r/b.md"])
    # 検証
    assert read_lines(state_dir / f"{session_id}.guided.txt") == ["/r/a.md", "/r/b.md"]
    assert not (state_dir / f"{session_id}.txt").exists()


def test_append_guided_when_unwritable(
    state_dir: Path,
    session_id: str,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """追記できないとき RecordWriteError にする（異常系）。"""
    # 準備
    state_dir.mkdir()
    unwritable(state_dir, 0o500)
    # 実行・検証
    with pytest.raises(RecordWriteError) as excinfo:
        service.append_guided(state_dir, session_id, ["/r/a.md"])
    assert excinfo.value.path == str(state_dir / f"{session_id}.guided.txt")


def test_delete_guided(
    state_dir: Path,
    session_id: str,
    write_record: Callable[[Sequence[str]], Path],
    write_guided: Callable[[Sequence[str]], Path],
) -> None:
    """案内済みの記録ファイルだけを消す（正常系）。"""
    # 準備
    record_file = write_record(["/r/a.md"])
    guided_file = write_guided(["/r/b.md"])
    # 実行
    service.delete_guided(state_dir, session_id)
    # 検証
    assert not guided_file.exists()
    assert record_file.exists()


def test_delete_guided_when_missing(state_dir: Path, session_id: str) -> None:
    """ファイルが無ければ何もしない（正常系）。"""
    # 実行
    service.delete_guided(state_dir, session_id)
    # 検証
    assert not state_dir.exists()


def test_delete_guided_when_undeletable(
    state_dir: Path,
    session_id: str,
    write_guided: Callable[[Sequence[str]], Path],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """消せない案内済みの記録ファイルを RecordDeleteError にする（異常系）。"""
    # 準備
    guided_file = write_guided(["/r/b.md"])
    unwritable(state_dir, 0o555)
    # 実行・検証
    with pytest.raises(RecordDeleteError) as excinfo:
        service.delete_guided(state_dir, session_id)
    assert excinfo.value.path == str(guided_file)


def test_append_history(
    state_dir: Path,
    session_id: str,
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """場所ごとに JSON を 1 行ずつ追記する（正常系）。"""

    def fixed_now() -> datetime:
        """固定した現在の時刻を返す。"""
        return datetime(2026, 10, 24, 9, 30, 0, 500_000, tzinfo=UTC)

    # 実行
    append_history(
        state_dir,
        session_id,
        ["/r/a.md", "/r/b.md"],
        method=ReadMethod.MCP,
        tool="mcp__docs__get_doc",
        now=fixed_now,
    )
    # 検証
    assert read_history() == [
        {
            "time": "2026-10-24T09:30:00Z",
            "session_id": session_id,
            "method": "mcp",
            "tool": "mcp__docs__get_doc",
            "location": "/r/a.md",
        },
        {
            "time": "2026-10-24T09:30:00Z",
            "session_id": session_id,
            "method": "mcp",
            "tool": "mcp__docs__get_doc",
            "location": "/r/b.md",
        },
    ]
    assert not (state_dir / f"{session_id}.txt").exists()


def test_append_history_when_empty(state_dir: Path, session_id: str) -> None:
    """空なら書かない（正常系）。"""
    # 実行
    append_history(state_dir, session_id, [], method=ReadMethod.READ, tool="Read")
    # 検証
    assert not state_dir.exists()


def test_append_history_when_unwritable(state_dir: Path, session_id: str) -> None:
    """書けないとき HistoryWriteError にする（異常系）。"""
    # 準備
    history = state_dir / f"{session_id}.history.jsonl"
    history.mkdir(parents=True)
    # 実行・検証
    with pytest.raises(HistoryWriteError) as excinfo:
        append_history(state_dir, session_id, ["/r/a.md"], method=ReadMethod.READ, tool="Read")
    assert excinfo.value.path == str(history)
