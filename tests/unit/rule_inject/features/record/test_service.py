"""features/record/service.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from rule_inject.features.record.service import (
    append_record,
    delete_record,
    is_valid_session_id,
    read_record,
    record_exists,
)
from rule_inject.shared.errors import RecordDeleteError, RecordReadError, RecordWriteError


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
