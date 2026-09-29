"""read_rules の応答の型と、URL の取得の関数型。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# URL と待ち時間（秒）を受けて本文を返す。失敗は FetchError（テストで差し替える）
type FetchUrlFn = Callable[[str, float], str]


@dataclass(frozen=True, slots=True, kw_only=True)
class RulePage:
    """返すルールの本文 1 件。"""

    location: str
    body: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FetchFailure:
    """取得できなかった場所 1 件。"""

    location: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadRulesResult:
    """返す本文・次に回す場所・取得できなかった場所。"""

    pages: list[RulePage] = field(default_factory=list)
    # 上限に収まらず返さなかった場所
    deferred: list[str] = field(default_factory=list)
    failures: list[FetchFailure] = field(default_factory=list)
