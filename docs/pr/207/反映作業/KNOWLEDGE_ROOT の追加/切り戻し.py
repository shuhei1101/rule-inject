"""KNOWLEDGE_ROOT の追加の切り戻し: 認証領域ごとに、実行で退避した最新の settings.json.bak-{日時}-knowledge-root を書き戻す。"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from targets import BACKUP_SUFFIX, SETTINGS_FILES

failed = False
for path in SETTINGS_FILES:
    # 実行が取った退避だけを選ぶ（ほかの作業の退避は書き戻さない）。名前の日時の順で最新を書き戻す
    backups = sorted(path.parent.glob(f"{path.name}.bak-*-{BACKUP_SUFFIX}"))
    if not backups:
        print(f"{path} の退避したファイル: failed")
        failed = True
        continue
    shutil.copy2(backups[-1], path)
    print(f"{path}: changed（{backups[-1].name}）")
sys.exit(1 if failed else 0)
