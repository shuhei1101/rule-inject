"""セッションごとの既読の記録ファイルと案内済みの記録ファイルの読み・追記・削除・掃除。"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from rule_inject.shared.errors import (
    RecordDeleteError,
    RecordReadError,
    RecordWriteError,
    describe,
)

# 記録ファイル名に使える session_id の形
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
RECORD_SUFFIX = ".txt"
# 案内済みの記録ファイルは `{session_id}{GUIDED_SUFFIX}`
GUIDED_SUFFIX = ".guided.txt"
# 他のプロセスと同時に追記しても行が混ざらないよう、追記専用で開くときのフラグ
APPEND_FLAGS = os.O_WRONLY | os.O_APPEND | os.O_CREAT
RECORD_FILE_MODE = 0o600
SECONDS_PER_DAY = 86_400


def _record_path(state_dir: Path, session_id: str, suffix: str = RECORD_SUFFIX) -> Path:
    """そのセッションの記録ファイル（既読か案内済み）のパスを返す。"""
    return state_dir / f"{session_id}{suffix}"


def is_valid_session_id(session_id: object) -> bool:
    """session_id が記録ファイル名に使える形かを返す。"""
    return isinstance(session_id, str) and SESSION_ID_PATTERN.fullmatch(session_id) is not None


def _read_lines(path: Path) -> frozenset[str]:
    """記録ファイルの場所の集合を返す（ファイルが無ければ空）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # 記録が無いのは失敗ではなく、まだ何も読んでいない状態
        return frozenset()
    except OSError as exc:
        raise RecordReadError(path=str(path), reason=describe(exc)) from exc
    # 空行を除いた行を集合にする（重なりは 1 つになる）
    return frozenset(line for line in text.splitlines() if line)


def _append_lines(state_dir: Path, path: Path, locations: Sequence[str]) -> None:
    """場所を 1 行ずつ記録ファイルへ追記する（空なら書かない）。"""
    if not locations:
        return
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RecordWriteError(path=str(state_dir), reason=describe(exc)) from exc
    # 全行を 1 つにまとめ、追記専用で 1 回に書く
    data = "".join(f"{location}\n" for location in locations).encode("utf-8")
    try:
        descriptor = os.open(path, APPEND_FLAGS, RECORD_FILE_MODE)
        try:
            written = os.write(descriptor, data)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise RecordWriteError(path=str(path), reason=describe(exc)) from exc
    # 一部だけ書けた行は次の追記と混ざるため、失敗として扱う
    if written != len(data):
        raise RecordWriteError(path=str(path), reason="記録の一部しか書けませんでした")


def _delete_file(path: Path) -> None:
    """記録ファイルを消す（ファイルが無ければ何もしない）。"""
    try:
        path.unlink()
    except FileNotFoundError:
        # 消す記録が無ければ、消した状態と同じ
        return
    except OSError as exc:
        raise RecordDeleteError(path=str(path), reason=describe(exc)) from exc


def read_record(state_dir: Path, session_id: str) -> frozenset[str]:
    """そのセッションの既読の場所の集合を返す（ファイルが無ければ空）。"""
    return _read_lines(_record_path(state_dir, session_id))


def read_guided(state_dir: Path, session_id: str) -> frozenset[str]:
    """そのセッションで止めずに案内した場所の集合を返す（ファイルが無ければ空）。"""
    return _read_lines(_record_path(state_dir, session_id, GUIDED_SUFFIX))


def append_record(state_dir: Path, session_id: str, locations: Sequence[str]) -> None:
    """場所を 1 行ずつ記録ファイルへ追記する。"""
    _append_lines(state_dir, _record_path(state_dir, session_id), locations)


def append_guided(state_dir: Path, session_id: str, locations: Sequence[str]) -> None:
    """止めずに案内した場所を 1 行ずつ案内済みの記録ファイルへ追記する。"""
    _append_lines(state_dir, _record_path(state_dir, session_id, GUIDED_SUFFIX), locations)


def delete_record(state_dir: Path, session_id: str) -> None:
    """そのセッションの記録ファイルを消す（ファイルが無ければ何もしない）。"""
    _delete_file(_record_path(state_dir, session_id))


def delete_guided(state_dir: Path, session_id: str) -> None:
    """そのセッションの案内済みの記録ファイルを消す（ファイルが無ければ何もしない）。"""
    _delete_file(_record_path(state_dir, session_id, GUIDED_SUFFIX))


def record_exists(state_dir: Path, session_id: str) -> bool:
    """そのセッションの記録ファイルがあるかを返す。"""
    return _record_path(state_dir, session_id).is_file()


def _swept_session_id(name: str) -> str | None:
    """掃除の対象の記録ファイルの名前から session_id を取り出し、対象の名前でなければ None を返す。"""
    # 案内済みの末尾を先に外す（`.guided.txt` も `.txt` で終わるため）
    for suffix in (GUIDED_SUFFIX, RECORD_SUFFIX):
        if name.endswith(suffix):
            session_id = name.removesuffix(suffix)
            return session_id if is_valid_session_id(session_id) else None
    return None


def sweep_records(
    state_dir: Path,
    keep_session_id: str,
    *,
    now: Callable[[], float] = time.time,
    retention_days: int,
) -> tuple[RecordDeleteError, ...]:
    """保持期間を過ぎた別のセッションの既読の記録ファイルと案内済みの記録ファイルを消し、消せなかったものを返す。"""
    try:
        entries = list(os.scandir(state_dir))
    except FileNotFoundError:
        # 記録フォルダがまだ無ければ掃除するものが無い（フォルダは作らない）
        return ()
    # この時刻より前に更新された記録ファイルが、保持期間を過ぎたもの
    threshold = now() - retention_days * SECONDS_PER_DAY
    failures: list[RecordDeleteError] = []
    for entry in entries:
        # 記録ファイルの名前でなければ対象にしない
        entry_session_id = _swept_session_id(entry.name)
        if entry_session_id is None or entry_session_id == keep_session_id:
            continue
        # シンボリックリンクとフォルダは辿らず、通常のファイルだけを対象にする
        if not entry.is_file(follow_symlinks=False):
            continue
        try:
            # 既読の記録と案内済みの記録は、それぞれ自分の最終更新で比べる
            expired = entry.stat(follow_symlinks=False).st_mtime < threshold
            if expired:
                os.unlink(entry.path)
        except FileNotFoundError:
            # 別のセッションが先に消していれば、消した状態と同じ
            continue
        except OSError as exc:
            # 消せないものは集め、残りの掃除を続ける
            failures.append(RecordDeleteError(path=entry.path, reason=describe(exc)))
    return tuple(failures)
