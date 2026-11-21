"""KNOWLEDGE_ROOT の追加の切り戻し: 実行で退避した最新の settings.json.bak-* を書き戻す。"""

import shutil
import sys
from pathlib import Path

SETTINGS = Path("/home/shuhei2441/.claude/settings.json")
backups = sorted(SETTINGS.parent.glob(f"{SETTINGS.name}.bak-*"))
if not backups:
    print("退避したファイル: failed")
    sys.exit(1)
shutil.copy2(backups[-1], SETTINGS)
print(f"設定の書き戻し: changed（{backups[-1]}）")
