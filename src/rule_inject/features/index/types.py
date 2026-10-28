"""索引の型（操作の種別・エントリ・照合の結果・読み込みの結果）。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, get_args

from rule_inject.shared.errors import IndexReadError

# エントリの `on`・`default_on` と呼ばれた操作の種別
type Operation = Literal["read", "write", "mcp"]

OPERATIONS: tuple[Operation, ...] = get_args(Operation.__value__)
# 索引を読んだときのエントリごとの扱い（照合に使う・読み飛ばした・無効）
type EntryStatus = Literal["effective", "skipped", "disabled"]

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
class ReadByCondition:
    """エントリの `read_by` の 1 要素（パターンはコンパイル済み）。"""

    # 当てる MCP のツールの完全名のパターン。どれか 1 つに当たればよい
    tools: tuple[MatchPattern, ...]
    # 引数の条件。全てが当たるときだけ要素を当てる（空なら引数では絞らない）
    args: tuple[ArgCondition, ...]


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
    # そのルールを既読にする MCP のツールの呼び出しの条件。どれか 1 つに当たれば既読にする（空なら MCP のツールでは既読にしない）
    read_by: tuple[ReadByCondition, ...]


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
class EntryOutcome:
    """索引の 1 エントリの位置・書かれた値・バージョンと、照合に使うか。"""

    # 索引の `rules` の中の位置（0 始まり）
    position: int
    # `parse_index` が読んだエントリのキーと値（書かれたまま）
    raw: Mapping[str, Any]
    # `entry_rev(raw)`
    rev: str
    status: EntryStatus
    # 状態が `effective` のときだけ持つ、場所を解きパターンをコンパイルしたエントリ
    entry: IndexEntry | None
    # 状態が `skipped` のときだけ持つ、読み飛ばした理由（フックが案内に載せる文言）
    reason: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexContent:
    """読めた索引 1 つのエントリごとの読み取り結果。"""

    # 索引の場所
    path: str
    # `rules` の並びの順のエントリごとの結果
    outcomes: tuple[EntryOutcome, ...]
