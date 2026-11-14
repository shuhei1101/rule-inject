#!/usr/bin/env python3
"""端末の設定の rule-inject の rule_indexes に docs/rules.yaml が無く、直下の rules.yaml が残っているかを読むだけで確かめる。"""

import sys
from pathlib import Path

from ruamel.yaml import YAML

SETTINGS = Path.home() / ".config/ai-monitor/settings.yaml"
REMOVED = "/mnt/c/Users/shuhe/repo/rule-inject/docs/rules.yaml"
KEPT = "/mnt/c/Users/shuhe/repo/rule-inject/rules.yaml"

data = YAML(typ="safe").load(SETTINGS.read_text(encoding="utf-8")) or {}
indexes = next(
    (
        list(p.get("rule_indexes") or [])
        for p in data.get("projects") or []
        if p.get("name") == "rule-inject"
    ),
    None,
)
print(f"rule-inject の rule_indexes: {indexes}")
if indexes is not None and REMOVED not in indexes and KEPT in indexes:
    print("rule_indexes の値: ok")
    sys.exit(0)
print("rule_indexes の値: failed")
sys.exit(1)
