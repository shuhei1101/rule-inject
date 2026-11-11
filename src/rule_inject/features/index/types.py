"""索引の型（操作の種別・エントリ・照合の結果・読み込みの結果）。"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, get_args

from rule_inject.shared.errors import IndexReadError

# エントリの `on`・`default_on` と呼ばれた操作の種別
type Operation = Literal["read", "write", "mcp"]

OPERATIONS: tuple[Operation, ...] = get_args(Operation.__value__)
# 索引を読んだときのエントリごとの扱い（照合に使用する・読み飛ばした・無効）
type EntryStatus = Literal["effective", "skipped", "disabled"]

# 索引が `default_on` を記載しないときの止める操作
DEFAULT_ON: tuple[Operation, ...] = OPERATIONS
# `args` のキーを、ドットの道筋と条件の木の `field` に分ける正規表現。該当しないキーは全体をドットの道筋として読む
TREE_KEY_PATTERN = re.compile(r"^(?P<path>[^\[\]]+)\[(?P<field>[^\[\]]+)\]$")


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchPattern:
    """索引に書き込まれた glob か正規表現のパターン 1 つ（正規表現はコンパイル済み）。"""

    # 索引に書き込まれたままのパターン（`re:` を含む）
    source: str
    # `re:` で始まるパターンの、`re:` を除いてコンパイルした正規表現。glob のときは None
    regex: re.Pattern[str] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ArgCondition:
    """エントリの `args` の 1 キーと、その値に照合するパターン。"""

    # 引数のキー。オブジェクトの子はドットで結ぶ（例 `filter.kind`・`filter[tags]`）
    key: str
    # どれか 1 つに該当すれば、そのキーは該当する
    patterns: tuple[MatchPattern, ...]
    # ドットで結んだ引数の道筋。`key` が `TREE_KEY_PATTERN` に該当すればその `path`、該当しなければ `key` のまま
    path: str = dataclasses.field(init=False)
    # 道筋の値を条件の木として読むときの `field`。ドットの道筋のキーは None
    field: str | None = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        """キーを道筋と `field` に分けて持つ（照合のたびに分け修正しない）。"""
        tree_key = TREE_KEY_PATTERN.match(self.key)
        # frozen のため object.__setattr__ で入れる
        object.__setattr__(self, "path", tree_key["path"] if tree_key else self.key)
        object.__setattr__(self, "field", tree_key["field"] if tree_key else None)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadByCondition:
    """エントリの `read_by` の 1 要素（パターンはコンパイル済み）。"""

    # 照合する MCP のツールの完全名のパターン。どれか 1 つに該当すればよい
    tools: tuple[MatchPattern, ...]
    # 引数の条件。全てが該当するときだけ要素を照合する（空なら引数では絞らない）
    args: tuple[ArgCondition, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadTool:
    """エントリの `read_tool`。案内に記載し、一致する呼び出しを既読にする（パターンでなく値）。"""

    # MCP のツールの完全名（`mcp__` で始まる）
    tool: str
    # 既読の判定に使用する引数。`args` の JSON の文字列を読んだオブジェクト（キーの順を保つ）
    args: Mapping[str, Any]
    # 案内に「省略可」として記載し、既読の判定には使用しない引数
    optional_args: Mapping[str, Any]


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexEntry:
    """索引の 1 エントリ（場所を解決し、`on` を埋めた後）。"""

    # 解決後のルールの場所（絶対パスか URL）
    location: str
    # 照合するパスのパターン
    paths: tuple[MatchPattern, ...]
    # 除外するパスのパターン
    exclude: tuple[MatchPattern, ...]
    # 照合するツール名のパターン
    tools: tuple[MatchPattern, ...]
    # MCP のツールの引数の条件。全てが該当するときだけエントリを照合する（空なら引数では絞らない）
    args: tuple[ArgCondition, ...]
    # 止める操作
    on: frozenset[Operation]
    # そのルールを既読にする MCP のツールの呼び出しの条件。どれか 1 つに該当すれば既読にする（空なら MCP のツールでは既読にしない）
    read_by: tuple[ReadByCondition, ...]
    # ルールを参照する MCP のツールと引数。記載しないエントリは None
    read_tool: ReadTool | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchedRule:
    """ルールの場所ごとに 1 件へまとめた照合の結果。"""

    location: str
    # 該当したエントリのどれか 1 つでも操作の種別が `on` に入っていれば True
    blocking: bool
    # 該当したエントリの `read_tool`（同じ値は 1 つにし、該当した順）
    read_tools: tuple[ReadTool, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexLoadResult:
    """読めたエントリと読めなかった索引。"""

    entries: tuple[IndexEntry, ...]
    failures: tuple[IndexReadError, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class EntryOutcome:
    """索引の 1 エントリの位置・記載された値・バージョンと、照合に使用するか。"""

    # 索引の `rules` の中の位置（0 始まり）
    position: int
    # `parse_index` が読んだエントリのキーと値（記載されたまま）
    raw: Mapping[str, Any]
    # `entry_rev(raw)`
    rev: str
    status: EntryStatus
    # 状態が `effective` のときだけ持つ、場所を解きパターンをコンパイルしたエントリ
    entry: IndexEntry | None
    # 状態が `skipped` のときだけ持つ、読み飛ばした理由（フックが案内に記載する文言）
    reason: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexContent:
    """読めた索引 1 つのエントリごとの読み取り結果。"""

    # 索引の場所
    path: str
    # `rules` の並びの順のエントリごとの結果
    outcomes: tuple[EntryOutcome, ...]
