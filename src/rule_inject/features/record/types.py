"""既読の記録・既読の履歴の型（既読の行・読み方）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal


class ReadMethod(StrEnum):
    """既読の履歴の `method` の値。"""

    # Read で読んだ
    READ = "read"
    # Bash の読むコマンドで読んだ
    BASH = "bash"
    # MCP のツールの結果の文書か、`read_by` に当たった MCP のツールの呼び出しで読んだ
    MCP = "mcp"


# 既読のルールの今の本文と既読にした時点の本文の関係（現在の本文と同じ・変わった・ファイルが無い）
type ReadState = Literal["current", "changed", "missing"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadEntry:
    """既読の記録の 1 行。"""

    # ルールの場所（解決後の絶対パス。改行とタブを含まない）
    location: str
    # 既読にした時点のルールのファイルの中身の SHA-256（`sha256:{16 進数}`）
    hash: str


@dataclass(frozen=True, slots=True, kw_only=True)
class HistoryEntry:
    """既読の履歴（`.history.jsonl`）の 1 行。"""

    # 既読にした時刻（`HISTORY_TIME_FORMAT` の UTC）
    time: str
    # 読み方
    method: ReadMethod
    # 既読にしたツールの名前
    tool: str
    # 既読にしたルールの場所
    location: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RecordSession:
    """記録フォルダに既読の記録ファイルを持つセッション 1 つ。"""

    session_id: str
    # 既読の記録ファイルの最終更新の時刻（UTC のタイムゾーン付き）
    updated_at: datetime
    # 既読のルールの場所の数（重なりを落とす）
    rule_count: int
