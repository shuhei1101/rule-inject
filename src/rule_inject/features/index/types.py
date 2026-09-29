"""索引の型（操作の種別・エントリ・照合の結果・読み込みの結果）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

from rule_inject.shared.errors import IndexReadError

# エントリの `on`・`default_on` と呼ばれた操作の種別
type Operation = Literal["read", "write", "mcp"]

OPERATIONS: tuple[Operation, ...] = get_args(Operation.__value__)
# 索引が `default_on` を書かないときの止める操作
DEFAULT_ON: tuple[Operation, ...] = OPERATIONS


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexEntry:
    """索引の 1 エントリ（場所を解決し、`on` を埋めた後）。"""

    # 解決後のルールの場所（絶対パスか URL）
    location: str
    # 当てるパスの glob
    paths: tuple[str, ...]
    # 外すパスの glob
    exclude: tuple[str, ...]
    # 当てるツール名の glob
    tools: tuple[str, ...]
    # 止める操作
    on: frozenset[Operation]


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchedRule:
    """ルールの場所ごとに 1 件へまとめた照合の結果。"""

    location: str
    # 当たったエントリのどれか 1 つでも操作の種別が `on` に入っていれば True
    blocking: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexLoadResult:
    """読めたエントリと読めなかった索引。"""

    entries: tuple[IndexEntry, ...]
    failures: tuple[IndexReadError, ...]
