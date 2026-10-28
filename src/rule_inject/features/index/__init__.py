"""索引の読み込みと、パス・ツール名・既読にする呼び出しの照合。"""

from rule_inject.features.index.service import (
    entry_matches_path,
    entry_rev,
    entry_revs,
    load_indexes,
    match_path,
    match_read_by,
    match_tool,
    read_index,
    read_index_text,
    rule_locations,
)

__all__ = [
    "entry_matches_path",
    "entry_rev",
    "entry_revs",
    "load_indexes",
    "match_path",
    "match_read_by",
    "match_tool",
    "read_index",
    "read_index_text",
    "rule_locations",
]
