"""索引の読み込みと、パス・ツール名の照合。"""

from rule_inject.features.index.service import (
    load_indexes,
    match_path,
    match_tool,
    rule_locations,
)

__all__ = ["load_indexes", "match_path", "match_tool", "rule_locations"]
