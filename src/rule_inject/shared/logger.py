"""失敗した操作を日付ごとのログ（JSON Lines）へ書き、古いログを消す。"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from rule_inject.shared.errors import LogDeleteError, describe

# `{yyyymmdd}` に続くログのファイル名の後半
LOG_FILE_SUFFIX = "_rule-inject.log"
# 記録フォルダの直下に残った変更前のログの名前
LEGACY_LOG_FILE_NAME = "rule-inject.log"
# 日付ごとのログのファイル名（8 桁の数字と後半）
LOG_FILE_PATTERN = re.compile(r"([0-9]{8})" + re.escape(LOG_FILE_SUFFIX))


class Component(StrEnum):
    """ログの `component` の値（インターフェース定義の識別子）。"""

    RULE_GUIDE = "rule_guide"
    SESSION_ID_INJECTION = "session_id_injection"
    RECORD_READ = "record_read"
    DISCARD_READ = "discard_read"
    WORK_RULES = "work_rules"
    READ_RULES = "read_rules"
    SWEEP_READ = "sweep_read"


class LogOperation(StrEnum):
    """ログの `operation` の値（失敗した操作）。"""

    READ_INDEX = "read_index"
    READ_RECORD = "read_record"
    WRITE_RECORD = "write_record"
    DELETE_RECORD = "delete_record"
    UNEXPECTED = "unexpected"
    DELETE_LOG = "delete_log"


def _utc_now() -> datetime:
    """現在の UTC の時刻を返す。"""
    return datetime.now(UTC)


def _utc_today() -> date:
    """今日の UTC の日付を返す。"""
    return datetime.now(UTC).date()


def log_file_path(log_folder: Path, day: date) -> Path:
    """その日付のログのファイルのパスを返す。"""
    return log_folder / f"{day:%Y%m%d}{LOG_FILE_SUFFIX}"


def write_log(
    log_folder: Path,
    *,
    component: Component,
    operation: LogOperation,
    reason: str,
    session_id: str | None = None,
    path: str | None = None,
    now: Callable[[], datetime] = _utc_now,
) -> None:
    """失敗した操作をその時刻の日付のログに 1 行追記し、書けないときは標準エラー出力へ出す。"""
    # 時刻は 1 回だけ取り、行の time とファイルの日付を同じ時刻から決める
    moment = now()
    # ER 図「ログ」の列を持つ 1 行の JSON にする
    line = json.dumps(
        {
            "time": moment.isoformat(),
            "component": component.value,
            "session_id": session_id,
            "operation": operation.value,
            "path": path,
            "reason": reason,
        },
        ensure_ascii=False,
    )
    try:
        log_folder.mkdir(parents=True, exist_ok=True)
        with log_file_path(log_folder, moment.astimezone(UTC).date()).open(
            "a", encoding="utf-8"
        ) as log_file:
            log_file.write(line + "\n")
    except OSError:
        # フックの標準出力は JSON 専用のため、ログに書けない失敗は標準エラー出力へ逃がす
        print(line, file=sys.stderr)


def _file_date(name: str) -> date | None:
    """ログのファイル名から日付を読み、ログのファイル名でなければ None を返す。"""
    matched = LOG_FILE_PATTERN.fullmatch(name)
    if matched is None:
        return None
    digits = matched.group(1)
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        # 月日が暦に無い数字（20261399 など）はログのファイルとして扱わない
        return None


def sweep_logs(
    log_folder: Path,
    retention_days: int,
    *,
    today: Callable[[], date] = _utc_today,
) -> tuple[LogDeleteError, ...]:
    """日付が保持日数以上前のログのファイルを消し、消せなかったものを返す。"""
    try:
        entries = list(os.scandir(log_folder))
    except FileNotFoundError:
        # ログのフォルダがまだ無ければ掃除するものが無い（フォルダは作らない）
        return ()
    # この日付以前のログのファイルが、保持日数を過ぎたもの
    threshold = today() - timedelta(days=retention_days)
    failures: list[LogDeleteError] = []
    for entry in entries:
        # 日付ごとのログのファイル名でなければ対象にしない
        file_date = _file_date(entry.name)
        if file_date is None:
            continue
        # シンボリックリンクとフォルダは辿らず、通常のファイルだけを対象にする
        if not entry.is_file(follow_symlinks=False):
            continue
        if file_date > threshold:
            continue
        try:
            os.unlink(entry.path)
        except FileNotFoundError:
            # 別のセッションが先に消していれば、消した状態と同じ
            continue
        except OSError as exc:
            # 消せないものは集め、残りの掃除を続ける
            failures.append(LogDeleteError(path=entry.path, reason=describe(exc)))
    return tuple(failures)


def delete_legacy_log(state_folder: Path) -> LogDeleteError | None:
    """記録フォルダに残った変更前のログを消し、消せなければ失敗を返す。"""
    legacy_log = state_folder / LEGACY_LOG_FILE_NAME
    try:
        # シンボリックリンクを辿らずに調べ、通常のファイルだけを消す
        is_regular = stat.S_ISREG(legacy_log.lstat().st_mode)
    except FileNotFoundError:
        return None
    if not is_regular:
        return None
    try:
        legacy_log.unlink()
    except FileNotFoundError:
        # 別のセッションが先に消していれば、消した状態と同じ
        return None
    except OSError as exc:
        return LogDeleteError(path=str(legacy_log), reason=describe(exc))
    return None
