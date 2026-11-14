#!/usr/bin/env python3
"""実行スクリプトが退避した端末の設定を書き戻し、モニターに読み直させる。"""

import shutil
import sys
import urllib.request
from pathlib import Path

SETTINGS = Path.home() / ".config/ai-monitor/settings.yaml"
BACKUP = Path.home() / ".config/ai-monitor/settings.yaml.bak-pr180"
PORT_FILE = Path("/mnt/c/Users/shuhe/repo/ai-monitor/data/monitor.port")

if not BACKUP.is_file():
    print("退避したファイル: failed")
    print(f"$ test -f {BACKUP}\nファイルがありません", file=sys.stderr)
    sys.exit(1)
shutil.copy2(BACKUP, SETTINGS)
print("設定の書き戻し: changed")
try:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/reload", method="POST")
    with urllib.request.urlopen(req, timeout=60) as res:
        res.read()
except Exception as exc:  # noqa: BLE001
    print("設定の再読込: failed")
    print(f"$ POST /reload\n{exc}", file=sys.stderr)
    sys.exit(1)
print("設定の再読込: changed")
