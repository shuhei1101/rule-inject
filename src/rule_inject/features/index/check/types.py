"""索引のチェックの型（問題の種類・問題・チェックの結果）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rule_inject.features.index.types import MatchPattern

# 索引の問題の種類（インターフェース定義「索引のチェック」の応答の一覧に当たる）
type ProblemKind = Literal[
    "hook_error", "violation", "missing_rule", "skipped_entry", "unmatched_path"
]


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexProblem:
    """索引の 1 つの問題。"""

    kind: ProblemKind
    # 索引の中の場所。キーは `.`、リストの要素は `[位置]` で結ぶ。索引全体にかかるときは `$`
    location: str
    # 理由（`violation` は `jsonschema` の `message`、`missing_rule`・`unmatched_path` は解いたルールの場所）
    reason: str
    # 問題のあるエントリの位置。エントリに属さない問題は None
    position: int | None
    # 問題のあるエントリのバージョン。エントリに属さない問題は None
    rev: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexCheck:
    """索引 1 つの問題の一覧。"""

    index: str
    # 見つかった問題。`hook_error` があるときはその 1 件だけ
    problems: tuple[IndexProblem, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ScanCursor:
    """辿る時間の上限で止まったときの続きの位置。文字列への変換はサーバーが行う。"""

    # 辿り終えた最後のファイルの、`project_dir` からの `/` 区切りのパス
    last_file: str
    # 最初の呼び出しから辿ったファイルの数
    scanned_files: int
    # まだ当たっていないエントリの索引・位置・バージョン
    unmatched: tuple[tuple[str, int, str], ...]
    # 確かめるエントリの一覧（索引・位置・バージョン）の SHA-256 の 16 進数
    fingerprint: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnmatchedScan:
    """1 回の呼び出しで辿った、`paths` の当たらないエントリの検出の結果。"""

    # 最後まで辿れたか
    completed: bool
    # 最初の呼び出しから辿ったファイルの数
    scanned_files: int
    # 索引ごとの `unmatched_path` の問題（渡された索引の順、問題は位置の順）。`completed` が False のときはどの索引も空
    checks: tuple[IndexCheck, ...]
    # 続きの位置。`completed` が True のときは None
    next_cursor: ScanCursor | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TagPattern:
    """効いているエントリの `args`・`read_by[].args` の、タグに当てるパターン 1 つとその場所。"""

    # 索引の場所
    index: str
    # エントリの位置
    position: int
    # エントリのバージョン（`entry_rev`）
    rev: str
    # パターンを書いた条件の場所。`args` か `read_by[{要素の位置}].args`
    location: str
    # パターンを書いたキー（`ArgCondition.key`。例 `filter[tags]`）
    key: str
    # パターン。応答には索引に書いたまま（`source`）を載せる
    pattern: MatchPattern
