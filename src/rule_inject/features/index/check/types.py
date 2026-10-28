"""索引のチェックの型（問題の種類・問題・チェックの結果）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# 索引の問題の種類（インターフェース定義「索引のチェック」の応答の一覧に当たる）
type ProblemKind = Literal["hook_error", "violation", "missing_rule", "skipped_entry"]


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexProblem:
    """索引の 1 つの問題。"""

    kind: ProblemKind
    # 索引の中の場所。キーは `.`、リストの要素は `[位置]` で結ぶ。索引全体にかかるときは `$`
    location: str
    # 理由（`violation` は `jsonschema` の `message`、`missing_rule` は解いたルールの場所）
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
