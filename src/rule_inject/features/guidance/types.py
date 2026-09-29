"""案内文の組み立てが読むルールの最小の型。"""

from __future__ import annotations

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
