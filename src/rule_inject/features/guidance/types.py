"""案内文の組み立てが読むルールの最小の型。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class GuidedReadTool(Protocol):
    """案内する参照のツール（`ツール:` の行に記載する属性だけを持つ型）。"""

    @property
    def tool(self) -> str:
        """MCP のツールの完全名。"""
        ...

    @property
    def args(self) -> Mapping[str, Any]:
        """引数のオブジェクト（索引に書き込んだキーの順）。"""
        ...

    @property
    def optional_args(self) -> Mapping[str, Any]:
        """省略してよい引数のオブジェクト。"""
        ...


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

    @property
    def read_tools(self) -> Sequence[GuidedReadTool]:
        """ルールを参照する MCP のツールと引数（パスの行の下に記載する順）。"""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class Guidance:
    """組み立てた案内文と、上限に収まって記載したルールの場所。"""

    text: str
    # 案内文に記載したルールの場所（記載した順）。フックは shown だけを案内済みにする
    shown: tuple[str, ...]
