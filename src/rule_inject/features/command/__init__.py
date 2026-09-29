"""Bash のコマンドから読むファイルのパスを取り出す。"""

from rule_inject.features.command.service import (
    FULL_READ_COMMANDS,
    READ_COMMANDS,
    extract_read_paths,
)

__all__ = ["FULL_READ_COMMANDS", "READ_COMMANDS", "extract_read_paths"]
