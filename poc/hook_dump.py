"""PostToolUse の入力（stdin の JSON）をそのまま JSONL へ追記する PoC のフック。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    """stdin の JSON を POC_DUMP_PATH の JSONL へ 1 行で追記する。"""
    payload = json.load(sys.stdin)
    dump_path = Path(os.environ["POC_DUMP_PATH"])
    with dump_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
