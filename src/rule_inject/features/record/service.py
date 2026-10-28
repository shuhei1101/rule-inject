"""セッションごとの既読の記録ファイル・案内済みの記録ファイル・既読の履歴ファイルの読み・追記・削除・掃除。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from rule_inject.features.record.types import (
    HistoryEntry,
    ReadEntry,
    ReadMethod,
    ReadState,
    RecordSession,
)
from rule_inject.shared.errors import (
    HistoryWriteError,
    RecordDeleteError,
    RecordReadError,
    RecordWriteError,
    RuleInjectError,
    describe,
)

# 記録ファイル名に使える session_id の形式
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
RECORD_SUFFIX = ".txt"
# 案内済みの記録ファイルは `{session_id}{GUIDED_SUFFIX}`
GUIDED_SUFFIX = ".guided.txt"
# 既読の履歴ファイルは `{session_id}{HISTORY_SUFFIX}`
HISTORY_SUFFIX = ".history.jsonl"
# 本文のハッシュは `{HASH_PREFIX}{SHA-256 の 16 進数}`
HASH_PREFIX = "sha256:"
# 既読の記録の 1 行で、場所と本文のハッシュを区切る文字
FIELD_SEPARATOR = "\t"
# 他のプロセスと同時に追記しても行が混ざらないよう、追記専用で開くときのフラグ
APPEND_FLAGS = os.O_WRONLY | os.O_APPEND | os.O_CREAT
RECORD_FILE_MODE = 0o600
# 既読の履歴の `time`（UTC の ISO 8601、秒まで）
HISTORY_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SECONDS_PER_DAY = 86_400


def _utc_now() -> datetime:
    """現在の UTC の時刻を返す。"""
    return datetime.now(UTC)


def _record_path(state_dir: Path, session_id: str, suffix: str = RECORD_SUFFIX) -> Path:
    """そのセッションの記録ファイル（既読・案内済み・既読の履歴）のパスを返す。"""
    return state_dir / f"{session_id}{suffix}"


def is_valid_session_id(session_id: object) -> bool:
    """session_id が記録ファイル名に使える形式かを返す。"""
    return isinstance(session_id, str) and SESSION_ID_PATTERN.fullmatch(session_id) is not None


def _read_lines(path: Path) -> tuple[str, ...]:
    """記録ファイルの空行を除いた行を、行の順に返す（ファイルが無ければ空）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # 記録が無いのは失敗ではなく、まだ何も読んでいない状態
        return ()
    except OSError as exc:
        raise RecordReadError(path=str(path), reason=describe(exc)) from exc
    return tuple(line for line in text.splitlines() if line)


def _append_lines(
    state_dir: Path,
    path: Path,
    lines: Sequence[str],
    error: type[RuleInjectError] = RecordWriteError,
) -> None:
    """行を 1 行ずつ記録ファイルへ追記する（空なら書かない）。書けないときは error を送出する。"""
    if not lines:
        return
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise error(path=str(state_dir), reason=describe(exc)) from exc
    # 全行を 1 つにまとめ、追記専用で 1 回に書く
    data = "".join(f"{line}\n" for line in lines).encode("utf-8")
    try:
        descriptor = os.open(path, APPEND_FLAGS, RECORD_FILE_MODE)
        try:
            written = os.write(descriptor, data)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise error(path=str(path), reason=describe(exc)) from exc
    # 一部だけ書けた行は次の追記と混ざるため、失敗として扱う
    if written != len(data):
        raise error(path=str(path), reason="記録の一部しか書けませんでした")


def _delete_file(path: Path) -> None:
    """記録ファイルを削除する（ファイルが無ければ何もしない）。"""
    try:
        path.unlink()
    except FileNotFoundError:
        # 削除する記録が無ければ、削除した状態と同じ
        return
    except OSError as exc:
        raise RecordDeleteError(path=str(path), reason=describe(exc)) from exc


def list_read_entries(state_dir: Path, session_id: str) -> tuple[ReadEntry, ...]:
    """そのセッションの既読の行を、記録ファイルの行の順に返す（ファイルが無ければ空）。ハッシュを持たない行は空のハッシュで残す。"""
    entries: list[ReadEntry] = []
    for line in _read_lines(_record_path(state_dir, session_id)):
        location, _, file_hash = line.partition(FIELD_SEPARATOR)
        # 場所が空の行は読み飛ばす
        if not location:
            continue
        # ハッシュを持たない行は、空のハッシュにして残す（確認のツールが changed として返すため）
        entries.append(
            ReadEntry(
                location=location,
                hash=file_hash if file_hash.startswith(HASH_PREFIX) else "",
            )
        )
    return tuple(entries)


def read_record(state_dir: Path, session_id: str) -> frozenset[ReadEntry]:
    """そのセッションの既読の行の集合を返す（ファイルが無ければ空）。ハッシュを持たない行は既読として扱わない。"""
    return frozenset(entry for entry in list_read_entries(state_dir, session_id) if entry.hash)


def read_guided(state_dir: Path, session_id: str) -> frozenset[str]:
    """そのセッションで止めずに案内した場所の集合を返す（ファイルが無ければ空）。"""
    # 重なりは 1 つになる
    return frozenset(_read_lines(_record_path(state_dir, session_id, GUIDED_SUFFIX)))


def append_record(state_dir: Path, session_id: str, entries: Sequence[ReadEntry]) -> None:
    """既読の行を `{場所}{FIELD_SEPARATOR}{ハッシュ}` の 1 行ずつ記録ファイルへ追記する。"""
    lines = [f"{entry.location}{FIELD_SEPARATOR}{entry.hash}" for entry in entries]
    _append_lines(state_dir, _record_path(state_dir, session_id), lines)


def append_guided(state_dir: Path, session_id: str, locations: Sequence[str]) -> None:
    """止めずに案内した場所を 1 行ずつ案内済みの記録ファイルへ追記する。"""
    _append_lines(state_dir, _record_path(state_dir, session_id, GUIDED_SUFFIX), locations)


def append_history(
    state_dir: Path,
    session_id: str,
    locations: Sequence[str],
    *,
    method: ReadMethod,
    tool: str,
    now: Callable[[], datetime] = _utc_now,
) -> None:
    """既読にした場所ごとに、時刻・セッション・読み方・ツール名・場所の JSON を 1 行ずつ既読の履歴へ追記する。"""
    if not locations:
        return
    # 時刻は 1 回だけ取り、全ての行に同じ秒までの UTC の時刻を入れる
    moment = now().astimezone(UTC).strftime(HISTORY_TIME_FORMAT)
    lines = [
        json.dumps(
            {
                "time": moment,
                "session_id": session_id,
                "method": method.value,
                "tool": tool,
                "location": location,
            },
            ensure_ascii=False,
        )
        for location in locations
    ]
    _append_lines(
        state_dir, _record_path(state_dir, session_id, HISTORY_SUFFIX), lines, HistoryWriteError
    )


def delete_record(state_dir: Path, session_id: str) -> None:
    """そのセッションの記録ファイルを削除する（ファイルが無ければ何もしない）。"""
    _delete_file(_record_path(state_dir, session_id))


def delete_guided(state_dir: Path, session_id: str) -> None:
    """そのセッションの案内済みの記録ファイルを削除する（ファイルが無ければ何もしない）。"""
    _delete_file(_record_path(state_dir, session_id, GUIDED_SUFFIX))


def record_exists(state_dir: Path, session_id: str) -> bool:
    """そのセッションの記録ファイルがあるかを返す。"""
    return _record_path(state_dir, session_id).is_file()


def _swept_session_id(name: str) -> str | None:
    """掃除の対象の記録ファイルの名前から session_id を取り出し、対象の名前でなければ None を返す。"""
    # 案内済みの末尾を先に外す（`.guided.txt` も `.txt` で終わるため）
    for suffix in (GUIDED_SUFFIX, HISTORY_SUFFIX, RECORD_SUFFIX):
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
    """保持期間を過ぎた別のセッションの既読の記録ファイル・案内済みの記録ファイル・既読の履歴ファイルを削除し、削除できなかったものを返す。"""
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
            # 既読の記録・案内済みの記録・既読の履歴は、それぞれ自分の最終更新で比べる
            expired = entry.stat(follow_symlinks=False).st_mtime < threshold
            if expired:
                os.unlink(entry.path)
        except FileNotFoundError:
            # 別のセッションが先に削除していれば、削除した状態と同じ
            continue
        except OSError as exc:
            # 削除できないものは集め、残りの掃除を続ける
            failures.append(RecordDeleteError(path=entry.path, reason=describe(exc)))
    return tuple(failures)


def hash_locations(locations: Sequence[str]) -> tuple[ReadEntry, ...]:
    """場所ごとに今のルールのファイルの本文のハッシュを取り、既読の行にして返す（読めない場所は含めない）。"""
    entries: list[ReadEntry] = []
    for location in locations:
        try:
            body = Path(location).read_bytes()
        except OSError:
            # 無い・フォルダ・権限が無い場所は、ハッシュを取れないため既読にしない
            continue
        digest = hashlib.sha256(body).hexdigest()
        entries.append(ReadEntry(location=location, hash=f"{HASH_PREFIX}{digest}"))
    return tuple(entries)


def current_read_locations(
    entries: frozenset[ReadEntry], locations: Iterable[str]
) -> frozenset[str]:
    """当たったルールの場所のうち、既読の行に場所と今の本文のハッシュの組があるものを返す。"""
    recorded = {entry.location for entry in entries}
    # 既読の行に場所が無いものは、ハッシュを取らずに未読とする
    candidates = [location for location in dict.fromkeys(locations) if location in recorded]
    current = hash_locations(candidates)
    return frozenset(entry.location for entry in current if entry in entries)


def list_rule_states(entries: Sequence[ReadEntry]) -> tuple[tuple[str, ReadState], ...]:
    """既読の行の場所ごとに、今の本文が既読にした時点と同じかを、場所が初めて現れた順に返す。"""
    locations = tuple(dict.fromkeys(entry.location for entry in entries))
    current_hashes = {entry.location: entry.hash for entry in hash_locations(locations)}
    recorded = frozenset(entries)
    states: list[tuple[str, ReadState]] = []
    for location in locations:
        # ハッシュを取れない場所はファイルが無いか読めない
        if location not in current_hashes:
            states.append((location, "missing"))
        # その場所のどれかの行のハッシュが今の本文のハッシュと同じなら既読
        elif ReadEntry(location=location, hash=current_hashes[location]) in recorded:
            states.append((location, "current"))
        else:
            states.append((location, "changed"))
    return tuple(states)


def _history_entry(line: str) -> HistoryEntry | None:
    """既読の履歴の 1 行を読む。読めない行・必要な値が文字列でない行・知らない読み方の行は None を返す。"""
    try:
        data = json.loads(line)
    except ValueError:
        # フックが追記している途中の行は、JSON として読めないことがある
        return None
    if not isinstance(data, dict):
        return None
    time_value, method, tool, location = (
        data.get("time"),
        data.get("method"),
        data.get("tool"),
        data.get("location"),
    )
    if not all(isinstance(value, str) for value in (time_value, method, tool, location)):
        return None
    if method not in {read_method.value for read_method in ReadMethod}:
        return None
    return HistoryEntry(time=time_value, method=ReadMethod(method), tool=tool, location=location)


def read_history(state_dir: Path, session_id: str) -> tuple[HistoryEntry, ...]:
    """そのセッションの既読の履歴を全行読み、読めた行を行の順に返す（ファイルが無ければ空）。"""
    lines = _read_lines(_record_path(state_dir, session_id, HISTORY_SUFFIX))
    entries = (_history_entry(line) for line in lines)
    return tuple(entry for entry in entries if entry is not None)


def list_record_sessions(state_dir: Path) -> tuple[RecordSession, ...]:
    """記録フォルダの既読の記録ファイルを持つセッションを、最終更新の新しい順に返す（記録フォルダが無ければ空）。"""
    try:
        directory = list(os.scandir(state_dir))
    except FileNotFoundError:
        # 記録フォルダがまだ無ければセッションが無い（フォルダは作らない）
        return ()
    except OSError as exc:
        raise RecordReadError(path=str(state_dir), reason=describe(exc)) from exc
    sessions: list[RecordSession] = []
    for entry in directory:
        # 案内済みの記録も `.txt` で終わるため、先に除く
        if entry.name.endswith(GUIDED_SUFFIX) or not entry.name.endswith(RECORD_SUFFIX):
            continue
        session_id = entry.name.removesuffix(RECORD_SUFFIX)
        # 記録ファイル名に使えない名前と、シンボリックリンク・フォルダは対象にしない
        if not is_valid_session_id(session_id) or not entry.is_file(follow_symlinks=False):
            continue
        try:
            modified = entry.stat(follow_symlinks=False).st_mtime
        except FileNotFoundError:
            # 並べる間に削除されたファイルは飛ばす
            continue
        locations = {read.location for read in list_read_entries(state_dir, session_id)}
        sessions.append(
            RecordSession(
                session_id=session_id,
                updated_at=datetime.fromtimestamp(modified, UTC),
                rule_count=len(locations),
            )
        )
    return tuple(sorted(sessions, key=lambda session: session.updated_at, reverse=True))
