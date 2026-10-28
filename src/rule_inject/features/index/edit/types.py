"""索引の編集の型（編集の結果・索引ごとのロック・書き込みのチェック）。"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True, kw_only=True)
class EditResult:
    """書き込み・削除の結果。"""

    # 編集した索引の場所
    index: str
    # 書き込んだ・削除したエントリの位置
    position: int
    # 書き込んだ後のエントリのバージョン。削除のときは None
    rev: str | None
    # 削除したエントリの `rule`（索引に書いたまま）。書き込みのときは None
    rule: str | None
    # 索引のファイルを書き換えたか
    written: bool
    # 書き換えの前後の unified diff（前後 3 行）
    diff: str


class IndexLocks:
    """同じ索引への書き込み・削除を 1 つずつ行うための、索引の場所ごとの `threading.Lock`。"""

    def __init__(self) -> None:
        """ロックの一覧と、その追加を 1 つずつ行うロックを作る。"""
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def lock_for(self, index_path: str) -> threading.Lock:
        """索引の場所のロックを返す。無ければ作る。"""
        with self._guard:
            return self._locks.setdefault(index_path, threading.Lock())


class CheckChange(Protocol):
    """書く前と書いた後の索引の内容を受け、新しく出た問題を `{索引の中の場所}: {理由}` の行で返す。"""

    def __call__(
        self, index_path: str, before_text: str, after_text: str, changed_rev: str | None, /
    ) -> tuple[str, ...]:
        """新しく出た問題の行を返す。空なら書いてよい。"""
        ...
