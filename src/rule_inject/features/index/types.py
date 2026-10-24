"""索引の型（操作の種別・エントリ・照合の結果・読み込みの結果）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, get_args

from rule_inject.shared.errors import IndexReadError

# エントリの `on`・`default_on` と呼ばれた操作の種別
type Operation = Literal["read", "write", "mcp"]

OPERATIONS: tuple[Operation, ...] = get_args(Operation.__value__)
# 索引が `default_on` を書かないときの止める操作
DEFAULT_ON: tuple[Operation, ...] = OPERATIONS


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchPattern:
    """索引に書かれた glob か正規表現のパターン 1 つ（正規表現はコンパイル済み）。"""

    # 索引に書かれたままのパターン（`re:` を含む）
    source: str
    # `re:` で始まるパターンの、`re:` を除いてコンパイルした正規表現。glob のときは None
    regex: re.Pattern[str] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ArgCondition:
    """エントリの `args` の 1 キーと、その値に当てるパターン。"""

    # 引数のキー。オブジェクトの子はドットで結ぶ（例 `filter.kind`）
    key: str
    # どれか 1 つに当たれば、そのキーは当たる
    patterns: tuple[MatchPattern, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexEntry:
    """索引の 1 エントリ（場所を解決し、`on` を埋めた後）。"""

    # 解決後のルールの場所（絶対パスか URL）
    location: str
    # 当てるパスのパターン
    paths: tuple[MatchPattern, ...]
    # 外すパスのパターン
    exclude: tuple[MatchPattern, ...]
    # 当てるツール名のパターン
    tools: tuple[MatchPattern, ...]
    # MCP のツールの引数の条件。全てが当たるときだけエントリを当てる（空なら引数では絞らない）
    args: tuple[ArgCondition, ...]
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


@dataclass(frozen=True, slots=True, kw_only=True)
class RejectedLocation:
    """`read_rules` で読まないと決めた場所かパスと、その理由。"""

    # 渡された場所かパス（解けたものは解決後）
    location: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectedLocations:
    """読む場所の選び出しの結果。"""

    # 本文を読むルールの場所（解決後。重なりを落とし、並びを保つ）
    targets: tuple[str, ...]
    # 読まない場所かパス
    rejected: tuple[RejectedLocation, ...]
