"""索引のチェック（フックと同じ読み取り・JSON Schema・ルールの場所の実在・`paths` の当たらないエントリ）。サーバーの依存を使うため、フックからは読み込まない。"""

from rule_inject.features.index.check.scan import scan_unmatched
from rule_inject.features.index.check.service import (
    check_change,
    check_index,
    check_index_text,
    load_validator,
)
from rule_inject.features.index.check.types import ScanCursor, UnmatchedScan

__all__ = [
    "ScanCursor",
    "UnmatchedScan",
    "check_change",
    "check_index",
    "check_index_text",
    "load_validator",
    "scan_unmatched",
]
