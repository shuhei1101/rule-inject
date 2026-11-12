"""配信元 rule-inject の config が project-index.yaml を指し、配信されているかを読むだけで確かめる。"""

import json
import sys
import urllib.request

SOURCES_URL = "http://127.0.0.1:8781/_api/settings/sources"
NEW_CONFIG = "/mnt/c/Users/shuhe/repo/rule-inject/project-index.yaml"


def main() -> int:
    """観測した値を出し、効いていれば 0 で終える。"""
    try:
        with urllib.request.urlopen(SOURCES_URL, timeout=60) as response:
            view = json.load(response)
    except OSError as error:
        print("配信元 rule-inject: failed")
        print(f"GET {SOURCES_URL}: {error}", file=sys.stderr)
        return 1
    rows = [row for row in view["sources"] if row["id"] == "rule-inject"]
    if len(rows) != 1:
        print("配信元 rule-inject: failed")
        print(f"rule-inject の行が {len(rows)} 件あります", file=sys.stderr)
        return 1
    row = rows[0]
    print(f"config: {row['config']}")
    print(f"status: {row['status']}")
    if row["config"] == [NEW_CONFIG] and row["status"] == "serving":
        print("配信元 rule-inject: ok")
        return 0
    print("配信元 rule-inject: failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
