"""端末の設定と、配信している dev-docs のサーバーに読み取りだけでつながるかを確かめる。"""

import json
import sys
import urllib.request
from pathlib import Path

SETTINGS = Path("/home/shuhei2441/.config/dev-docs/settings.yaml")
SOURCES_URL = "http://127.0.0.1:8781/_api/settings/sources"


def main() -> int:
    """対象ごとに結果の行を出す。"""
    rc = 0
    if SETTINGS.is_file():
        print("端末の設定: ok")
    else:
        print("端末の設定: failed")
        print(f"{SETTINGS} がありません", file=sys.stderr)
        rc = 1
    try:
        with urllib.request.urlopen(SOURCES_URL, timeout=60) as response:
            json.load(response)
        print("dev-docs のサーバー: ok")
    except OSError as error:
        print("dev-docs のサーバー: failed")
        print(f"GET {SOURCES_URL}: {error}", file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
