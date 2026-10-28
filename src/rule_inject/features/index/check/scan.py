"""プロジェクトのファイルを辿り、`paths` がどのファイルにも当たらないエントリを返す。"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Iterator, Sequence

from rule_inject.features.index import entry_matches_path
from rule_inject.features.index.check.types import (
    IndexCheck,
    IndexProblem,
    ScanCursor,
    UnmatchedScan,
)
from rule_inject.features.index.types import IndexContent, IndexEntry

# プロジェクトのファイルを辿るときに中へ入らないフォルダの名前
SKIPPED_DIR_NAMES = frozenset({".git"})
PATH_SEPARATOR = "/"

# 確かめるエントリの索引・位置・バージョン
type EntryKey = tuple[str, int, str]


def _walk(
    directory: str, parts: tuple[str, ...], after_parts: tuple[str, ...] | None
) -> Iterator[str]:
    """フォルダの中を名前の順に読み、`after_parts` より後のファイルの相対パスを返す。"""
    try:
        entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
    except OSError:
        # 読めないフォルダは飛ばす
        return
    for entry in entries:
        entry_parts = (*parts, entry.name)
        # フォルダ（シンボリックリンクを辿らない）は、中の全てのファイルが `after_parts` 以前なら入らない
        if entry.is_dir(follow_symlinks=False):
            if entry.name in SKIPPED_DIR_NAMES:
                continue
            if after_parts is not None and entry_parts < after_parts[: len(entry_parts)]:
                continue
            yield from _walk(entry.path, entry_parts, after_parts)
        elif entry.is_file() and (after_parts is None or entry_parts > after_parts):
            yield PATH_SEPARATOR.join(entry_parts)


def _iter_project_files(project_dir: str, after: str | None) -> Iterator[str]:
    """`project_dir` の下のファイルを、パスの部分ごとの名前の順で `/` 区切りの相対パスにして返す。"""
    after_parts = tuple(after.split(PATH_SEPARATOR)) if after is not None else None
    yield from _walk(project_dir, (), after_parts)


def _fingerprint(keys: Sequence[EntryKey]) -> str:
    """確かめるエントリの索引・位置・バージョンの並びを SHA-256 の 16 進数にする。"""
    return hashlib.sha256(json.dumps([list(key) for key in keys]).encode("utf-8")).hexdigest()


def _candidates(contents: Sequence[IndexContent]) -> dict[EntryKey, IndexEntry]:
    """効いているエントリのうち `paths` を持つものを、索引・位置・バージョンの鍵で並べる。"""
    return {
        (content.path, outcome.position, outcome.rev): outcome.entry
        for content in contents
        for outcome in content.outcomes
        if outcome.status == "effective" and outcome.entry is not None and outcome.entry.paths
    }


def _checks(
    contents: Sequence[IndexContent],
    candidates: dict[EntryKey, IndexEntry],
    unmatched: set[EntryKey],
) -> tuple[IndexCheck, ...]:
    """当たらなかったエントリを、索引ごとの `unmatched_path` の問題にする。"""
    return tuple(
        IndexCheck(
            index=content.path,
            problems=tuple(
                IndexProblem(
                    kind="unmatched_path",
                    location=f"rules[{position}].paths",
                    reason=candidates[(path, position, rev)].location,
                    position=position,
                    rev=rev,
                )
                for path, position, rev in candidates
                if path == content.path and (path, position, rev) in unmatched
            ),
        )
        for content in contents
    )


def scan_unmatched(
    project_dir: str,
    contents: Sequence[IndexContent],
    *,
    cursor: ScanCursor | None,
    time_limit: float,
    clock: Callable[[], float] = time.monotonic,
) -> UnmatchedScan:
    """`project_dir` の下のファイルを辿り、効いているエントリのうち `paths` がどのファイルにも当たらないものを返す。時間の上限を超えたら続きの位置を返す。"""
    candidates = _candidates(contents)
    keys = tuple(candidates)
    fingerprint = _fingerprint(keys)
    # 続きの位置は、確かめるエントリの一覧が同じときだけ使う（違えば最初から辿る）
    if cursor is not None and cursor.fingerprint == fingerprint:
        unmatched = set(cursor.unmatched)
        after: str | None = cursor.last_file
        scanned = cursor.scanned_files
    else:
        unmatched = set(keys)
        after = None
        scanned = 0
    started = clock()
    last_file = after
    # まだ当たっていないエントリが無ければ、辿らない
    files = _iter_project_files(project_dir, after) if unmatched else iter(())
    for walked, relative in enumerate(files):
        # 1 回の呼び出しで少なくとも 1 つのファイルを当てるため、2 つ目以降のファイルの前に経過時間を見る
        if walked > 0 and clock() - started >= time_limit:
            next_cursor = ScanCursor(
                last_file=last_file or "",
                scanned_files=scanned,
                unmatched=tuple(key for key in keys if key in unmatched),
                fingerprint=fingerprint,
            )
            return UnmatchedScan(
                completed=False,
                scanned_files=scanned,
                checks=_checks(contents, candidates, set()),
                next_cursor=next_cursor,
            )
        path = os.path.join(project_dir, relative)
        # 当たったエントリは、残りのファイルに当てない
        unmatched = {key for key in unmatched if not entry_matches_path(candidates[key], path)}
        scanned += 1
        last_file = relative
        # 全てのエントリが当たったら、辿るのもやめる
        if not unmatched:
            break
    return UnmatchedScan(
        completed=True,
        scanned_files=scanned,
        checks=_checks(contents, candidates, unmatched),
        next_cursor=None,
    )
