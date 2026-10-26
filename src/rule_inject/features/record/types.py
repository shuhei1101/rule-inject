"""既読の履歴の型（読み方）。"""

from __future__ import annotations

from enum import StrEnum


class ReadMethod(StrEnum):
    """既読の履歴の `method` の値。"""

    # Read で読んだ
    READ = "read"
    # Bash の読むコマンドで読んだ
    BASH = "bash"
    # `read_by` に当たった MCP のツールを呼んだ
    MCP = "mcp"
