"""KNOWLEDGE_ROOT の追加の疎通確認: 書き換える settings.json と指す knowledge のクローンを読み取りだけで確かめる。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from targets import SETTINGS_FILES, VALUE

failed = False
for path in SETTINGS_FILES:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("env"), dict):
            raise ValueError("最上位か env がオブジェクトでない")
        print(f"{path}: ok")
    except (OSError, ValueError) as exc:
        print(f"{path}: failed")
        print(f"read {path}: {exc}", file=sys.stderr)
        failed = True
rule = Path(VALUE) / "docs" / "rule" / "python-core-naming.yaml"
if rule.is_file():
    print("knowledge のクローン: ok")
else:
    print("knowledge のクローン: failed")
    print(f"not found: {rule}", file=sys.stderr)
    failed = True
sys.exit(1 if failed else 0)
