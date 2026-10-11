"""案内文の組み立てが読むルールの最小の型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class GuidedRule(Protocol):
    """案内するルール（案内文の組み立てが読む属性だけを持つ型）。"""

    @property
    def location(self) -> str:
        """ルールの場所。"""
        ...

    @property
    def blocking(self) -> bool:
        """操作を止めるルールか。"""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class Guidance:
    """組み立てた案内文と、上限に収まって載せたルールの場所。"""

    text: str
    # 案内文に載せたルールの場所（載せた順）。フックは shown だけを案内済みにする
    shown: tuple[str, ...]
