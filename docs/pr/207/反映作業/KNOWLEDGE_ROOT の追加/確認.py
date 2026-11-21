"""KNOWLEDGE_ROOT の追加の確認: settings.json の env の値と、索引の 9 件が読める場所を指すかを観測する。"""

import json
import sys
from pathlib import Path

SETTINGS = Path("/home/shuhei2441/.claude/settings.json")
VALUE = "/home/shuhei2441/repo/knowledge/.claude/worktrees/develop"
RULES = (
    "python-core-naming",
    "python-core-type-hint",
    "python-core-language-rules",
    "python-architecture-layout",
    "python-architecture-dependency-management",
    "python-shared-logger",
    "python-testing-layers",
    "python-testing-mock",
    "python-core-style",
)

value = json.loads(SETTINGS.read_text(encoding="utf-8")).get("env", {}).get("KNOWLEDGE_ROOT")
print(f"env の KNOWLEDGE_ROOT: {'ok' if value == VALUE else 'failed'}（{value}）")
missing = [name for name in RULES if not (Path(VALUE) / "docs" / "rule" / f"{name}.yaml").is_file()]
print(f"ルール 9 件の場所: {'ok' if not missing else 'failed'}（無い: {missing}）")
sys.exit(0 if value == VALUE and not missing else 1)
