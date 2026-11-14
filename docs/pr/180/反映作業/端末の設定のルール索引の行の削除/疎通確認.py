#!/usr/bin/env python3
"""端末の設定と稼働中のモニターに、読み取りだけでつながるかを確かめる。"""

import sys
import urllib.request
from pathlib import Path

SETTINGS = Path.home() / ".config/ai-monitor/settings.yaml"
PORT_FILE = Path("/mnt/c/Users/shuhe/repo/ai-monitor/data/monitor.port")

failed = False
if SETTINGS.is_file():
    SETTINGS.read_text(encoding="utf-8")
    print("端末の設定: ok")
else:
    print("端末の設定: failed")
    print(f"$ test -f {SETTINGS}\nファイルがありません", file=sys.stderr)
    failed = True

try:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/openapi.json", timeout=10) as res:
        res.read()
    print("モニター: ok")
except Exception as exc:  # noqa: BLE001
    print("モニター: failed")
    print(f"$ GET http://127.0.0.1:<{PORT_FILE}>/openapi.json\n{exc}", file=sys.stderr)
    failed = True

sys.exit(1 if failed else 0)
