"""KNOWLEDGE_ROOT の追加の疎通確認: 書き換える設定ファイルと指す knowledge のクローンを読み取りだけで確かめる。"""

import json
import sys
from pathlib import Path

SETTINGS = Path("/home/shuhei2441/.claude/settings.json")
KNOWLEDGE_ROOT = Path("/home/shuhei2441/repo/knowledge/.claude/worktrees/develop")
RULE = KNOWLEDGE_ROOT / "docs" / "rule" / "python-core-naming.yaml"

failed = False
try:
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("最上位がオブジェクトでない")
    print("設定ファイル: ok")
except (OSError, ValueError) as exc:
    print("設定ファイル: failed")
    print(f"read {SETTINGS}: {exc}", file=sys.stderr)
    failed = True
if RULE.is_file():
    print("knowledge のクローン: ok")
else:
    print("knowledge のクローン: failed")
    print(f"not found: {RULE}", file=sys.stderr)
    failed = True
sys.exit(1 if failed else 0)
