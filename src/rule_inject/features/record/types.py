"""既読の記録・既読の履歴の型（既読の行・読み方）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReadMethod(StrEnum):
    """既読の履歴の `method` の値。"""

    # Read で読んだ
    READ = "read"
    # Bash の読むコマンドで読んだ
    BASH = "bash"
    # MCP のツールの結果の文書か、`read_by` に当たった MCP のツールの呼び出しで読んだ
    MCP = "mcp"


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadEntry:
    """既読の記録の 1 行。"""

    # ルールの場所（解決後の絶対パス。改行とタブを含まない）
    location: str
    # 既読にした時点のルールのファイルの中身の SHA-256（`sha256:{16 進数}`）
    hash: str
