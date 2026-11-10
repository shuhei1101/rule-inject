"""実行で退避した settings.json を戻し、作った settings.yaml を消す。

Usage:
# リポジトリの直下で 1 回だけ流す
python3 dev/pr/52/反映作業/利用者の設定ファイルへの移行/切り戻し.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from _migration import (
    CONFIG_ENV,
    CONFIG_PATH,
    MigrationError,
    backup_path,
    read_json,
    settings_files,
)


def _created_config(path: Path) -> bool:
    """実行が settings.json に RULE_INJECT_CONFIG を入れたか（= 実行が settings.yaml を作ったか）。"""
    current = read_json(path).get("env") or {}
    before = read_json(backup_path(path)).get("env") or {}
    return CONFIG_ENV in current and CONFIG_ENV not in before


def main() -> int:
    """settings.json の書き戻しと settings.yaml の削除の結果を出す。"""
    restored = [path for path in settings_files() if backup_path(path).is_file()]
    if not restored:
        print("退避したファイル: failed（settings.json.bak-rule-inject がありません）")
        return 1
    # 書き戻す前に、settings.yaml を実行が作ったかを判定する
    try:
        created = any(_created_config(path) for path in restored)
    except MigrationError as error:
        print(f"退避したファイル: failed（{error}）")
        return 1
    for path in restored:
        shutil.copy2(backup_path(path), path)
        backup_path(path).unlink()
        print(f"{path} の書き戻し: changed")
    # 実行が作った settings.yaml だけを削除する。既にあったものは残す
    if created and CONFIG_PATH.is_file():
        CONFIG_PATH.unlink()
        print(f"{CONFIG_PATH} の削除: changed")
    else:
        print(f"{CONFIG_PATH} の削除: skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
