"""セッションごとの既読の記録ファイルの読み・追記・削除。"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
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
# 他のプロセスと同時に追記しても行が混ざらないよう、追記専用で開くときのフラグ
APPEND_FLAGS = os.O_WRONLY | os.O_APPEND | os.O_CREAT
RECORD_FILE_MODE = 0o600


def _record_path(state_dir: Path, session_id: str) -> Path:
    """そのセッションの記録ファイルのパスを返す。"""
    return state_dir / f"{session_id}{RECORD_SUFFIX}"


def is_valid_session_id(session_id: object) -> bool:
    """session_id が記録ファイル名に使える形かを返す。"""
    return isinstance(session_id, str) and SESSION_ID_PATTERN.fullmatch(session_id) is not None


def read_record(state_dir: Path, session_id: str) -> frozenset[str]:
    """そのセッションの既読の場所の集合を返す（ファイルが無ければ空）。"""
    path = _record_path(state_dir, session_id)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # 記録が無いのは失敗ではなく、まだ何も読んでいない状態
        return frozenset()
    except OSError as exc:
        raise RecordReadError(path=str(path), reason=describe(exc)) from exc
    # 空行を除いた行を集合にする（重なりは 1 つになる）
    return frozenset(line for line in text.splitlines() if line)


def append_record(state_dir: Path, session_id: str, locations: Sequence[str]) -> None:
    """場所を 1 行ずつ記録ファイルへ追記する。"""
    if not locations:
        return
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RecordWriteError(path=str(state_dir), reason=describe(exc)) from exc
    path = _record_path(state_dir, session_id)
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


def delete_record(state_dir: Path, session_id: str) -> None:
    """そのセッションの記録ファイルを消す（ファイルが無ければ何もしない）。"""
    path = _record_path(state_dir, session_id)
    try:
        path.unlink()
    except FileNotFoundError:
        # 消す記録が無ければ、消した状態と同じ
        return
    except OSError as exc:
        raise RecordDeleteError(path=str(path), reason=describe(exc)) from exc


def record_exists(state_dir: Path, session_id: str) -> bool:
    """そのセッションの記録ファイルがあるかを返す。"""
    return _record_path(state_dir, session_id).is_file()
