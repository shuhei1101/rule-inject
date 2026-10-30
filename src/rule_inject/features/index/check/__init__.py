"""索引のチェック（フックと同じ読み取り・JSON Schema・ルールの場所の実在・`paths` の当たらないエントリ・使われていないタグのパターン）。サーバーの依存を使うため、フックからは読み込まない。"""

from rule_inject.features.index.check.scan import scan_unmatched
from rule_inject.features.index.check.service import (
    check_change,
    check_index,
    check_index_text,
    load_validator,
)
from rule_inject.features.index.check.tags import tag_patterns, unused_tag_patterns
from rule_inject.features.index.check.types import ScanCursor, TagPattern, UnmatchedScan

__all__ = [
    "ScanCursor",
    "TagPattern",
    "UnmatchedScan",
    "check_change",
    "check_index",
    "check_index_text",
    "load_validator",
    "scan_unmatched",
    "tag_patterns",
    "unused_tag_patterns",
]
