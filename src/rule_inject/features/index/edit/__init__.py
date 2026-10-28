"""索引のエントリの編集（`ruamel.yaml` の round-trip で書き換える）。サーバーの依存を使うため、フックからは読み込まない。"""

from rule_inject.features.index.edit.service import delete_entry, write_entry
from rule_inject.features.index.edit.types import IndexLocks

__all__ = ["IndexLocks", "delete_entry", "write_entry"]
