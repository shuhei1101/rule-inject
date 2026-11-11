"""MCP のツールの結果に載った文書の型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DocumentScope(StrEnum):
    """結果の文書の `scope` の値。"""

    # 文書の全文を記載した（既読になる）
    FULL = "full"
    # 文書の一部の見出しだけを記載した
    SECTION = "section"
    # 文書の説明だけを記載した
    SUMMARY = "summary"


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultDocument:
    """MCP のツールの結果に載った文書の場所と範囲。"""

    # 結果に載ったままの文書のパス（解いていない）
    path: str
    # 結果に載ったままの範囲（`DocumentScope` の値か、それ以外の文字列）
    scope: str
