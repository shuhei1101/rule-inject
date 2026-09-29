"""shared/logger.py の単体テスト。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from rule_inject.shared import errors, logger
from rule_inject.shared.logger import Component, LogOperation, write_log


def _fixed_now() -> datetime:
    """固定の UTC の時刻を返す。"""
    return datetime(2026, 9, 29, 8, 0, 0, tzinfo=UTC)


def _fixed_today() -> date:
    """固定の UTC の今日の日付を返す。"""
    return date(2026, 9, 29)


def test_write_log(
    log_folder: Path,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """ログに 1 行追記する（正常系）。"""
    # 実行
    write_log(
        log_folder,
        component=Component("read_rules"),
        operation=LogOperation("write_record"),
        reason="PermissionError: denied",
        session_id="s1",
        path="/p/state",
        now=_fixed_now,
    )
    # 検証
    lines = read_lines(log_folder / "20260929_rule-inject.log")
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "time": "2026-09-29T08:00:00+00:00",
        "component": "read_rules",
        "session_id": "s1",
        "operation": "write_record",
        "path": "/p/state",
        "reason": "PermissionError: denied",
    }


def test_write_log_when_unwritable(
    log_folder: Path,
    unwritable: Callable[[Path, int], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """書けないとき標準エラー出力へ出す（異常系）。"""
    # 準備
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    # 実行
    write_log(
        log_folder,
        component=Component("read_rules"),
        operation=LogOperation("write_record"),
        reason="PermissionError: denied",
        now=_fixed_now,
    )
    # 検証
    captured = capsys.readouterr()
    assert json.loads(captured.err.strip())["operation"] == "write_record"


def test_write_log_when_date_changes(
    log_folder: Path,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """日付が変わると別のファイルに書く（正常系）。"""
    # 実行
    write_log(
        log_folder,
        component=Component("read_rules"),
        operation=LogOperation("write_record"),
        reason="PermissionError: denied",
        now=lambda: datetime(2026, 9, 29, 23, 59, 59, tzinfo=UTC),
    )
    write_log(
        log_folder,
        component=Component("read_rules"),
        operation=LogOperation("write_record"),
        reason="PermissionError: denied",
        now=lambda: datetime(2026, 9, 30, 0, 0, 0, tzinfo=UTC),
    )
    # 検証
    assert len(read_lines(log_folder / "20260929_rule-inject.log")) == 1
    assert len(read_lines(log_folder / "20260930_rule-inject.log")) == 1


def test_log_file_path() -> None:
    """日付を頭に置いた名前になる（正常系）。"""
    # 実行
    result = logger.log_file_path(Path("/l"), date(2026, 9, 29))
    # 検証
    assert result == Path("/l/20260929_rule-inject.log")


def test_sweep_logs(
    log_folder: Path,
    write_dated_log: Callable[[date], Path],
) -> None:
    """日付が保持日数以上前のファイルだけを消す（正常系）。"""
    # 準備
    today_file = write_dated_log(date(2026, 9, 29))
    within_file = write_dated_log(date(2026, 9, 27))
    expired_file = write_dated_log(date(2026, 9, 26))
    # 実行
    result = logger.sweep_logs(log_folder, 3, today=_fixed_today)
    # 検証
    assert not expired_file.exists()
    assert within_file.exists()
    assert today_file.exists()
    assert result == ()


def test_sweep_logs_when_retention_too_long(
    log_folder: Path,
    write_dated_log: Callable[[date], Path],
) -> None:
    """暦の範囲を超えるほど大きい保持日数なら何も消さない（正常系）。"""
    # 準備
    old_file = write_dated_log(date(2020, 1, 1))
    # 実行
    result = logger.sweep_logs(log_folder, 999999, today=_fixed_today)
    # 検証
    assert old_file.exists()
    assert result == ()


def test_sweep_logs_when_not_log(
    tmp_path: Path,
    log_folder: Path,
) -> None:
    """ログのファイルでないものは消さない（正常系）。"""
    # 準備
    log_folder.mkdir()
    notes = log_folder / "notes.txt"
    notes.write_text("メモ\n", encoding="utf-8")
    short_date = log_folder / "2026_rule-inject.log"
    short_date.write_text("{}\n", encoding="utf-8")
    invalid_date = log_folder / "20261399_rule-inject.log"
    invalid_date.write_text("{}\n", encoding="utf-8")
    folder = log_folder / "20260101_rule-inject.log"
    folder.mkdir()
    link_target = tmp_path / "link-target.log"
    link_target.write_text("{}\n", encoding="utf-8")
    link = log_folder / "20260102_rule-inject.log"
    link.symlink_to(link_target)
    # 実行
    result = logger.sweep_logs(log_folder, 3, today=_fixed_today)
    # 検証
    assert notes.exists()
    assert short_date.exists()
    assert invalid_date.exists()
    assert folder.is_dir()
    assert link.is_symlink()
    assert link_target.exists()
    assert result == ()


def test_sweep_logs_when_missing(log_folder: Path) -> None:
    """ログのフォルダが無ければ何もしない（正常系）。"""
    # 実行
    result = logger.sweep_logs(log_folder, 3, today=_fixed_today)
    # 検証
    assert result == ()
    assert not log_folder.exists()


def test_sweep_logs_when_undeletable(
    log_folder: Path,
    write_dated_log: Callable[[date], Path],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """消せないログのファイルを返す（異常系）。"""
    # 準備
    expired_file = write_dated_log(date(2026, 9, 26))
    unwritable(log_folder, 0o555)
    # 実行
    result = logger.sweep_logs(log_folder, 3, today=_fixed_today)
    # 検証
    assert len(result) == 1
    assert isinstance(result[0], errors.LogDeleteError)
    assert result[0].path == str(expired_file)
    assert expired_file.exists()


def test_delete_legacy_log(state_dir: Path) -> None:
    """変更前のログを消す（正常系）。"""
    # 準備
    state_dir.mkdir()
    legacy_log = state_dir / "rule-inject.log"
    legacy_log.write_text("{}\n", encoding="utf-8")
    # 実行
    result = logger.delete_legacy_log(state_dir)
    # 検証
    assert result is None
    assert not legacy_log.exists()


def _no_state_folder(state_dir: Path) -> None:
    """記録フォルダが無い配置にする（何も置かない）。"""


def _no_legacy_log(state_dir: Path) -> None:
    """記録フォルダだけがあり、`rule-inject.log` が無い配置にする。"""
    state_dir.mkdir()


def _legacy_log_is_folder(state_dir: Path) -> None:
    """`rule-inject.log` がフォルダの配置にする。"""
    (state_dir / "rule-inject.log").mkdir(parents=True)


@pytest.mark.parametrize(
    ("layout", "remaining"),
    [
        pytest.param(_no_state_folder, [], id="no_state_folder"),
        pytest.param(_no_legacy_log, [], id="no_legacy_log"),
        pytest.param(_legacy_log_is_folder, ["rule-inject.log"], id="legacy_log_is_folder"),
    ],
)
def test_delete_legacy_log_when_missing(
    state_dir: Path,
    layout: Callable[[Path], None],
    remaining: list[str],
) -> None:
    """無ければ何もしない（正常系）。"""
    # 準備
    layout(state_dir)
    # 実行
    result = logger.delete_legacy_log(state_dir)
    # 検証
    assert result is None
    assert sorted(path.name for path in state_dir.glob("*")) == remaining


def test_delete_legacy_log_when_undeletable(
    state_dir: Path,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """消せないとき失敗を返す（異常系）。"""
    # 準備
    state_dir.mkdir()
    legacy_log = state_dir / "rule-inject.log"
    legacy_log.write_text("{}\n", encoding="utf-8")
    unwritable(state_dir, 0o555)
    # 実行
    result = logger.delete_legacy_log(state_dir)
    # 検証
    assert isinstance(result, errors.LogDeleteError)
    assert result.path == str(legacy_log)
    assert legacy_log.exists()
