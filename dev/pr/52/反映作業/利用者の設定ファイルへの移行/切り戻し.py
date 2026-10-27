"""実行で退避した settings.json を戻し、作った settings.yaml を消す。"""

from __future__ import annotations

import shutil
import sys

from _migration import CONFIG_PATH, backup_path, settings_files


def main() -> int:
    """settings.json の書き戻しと settings.yaml の削除の結果を出す。"""
    restored = [path for path in settings_files() if backup_path(path).is_file()]
    if not restored:
        print("退避したファイル: failed（settings.json.bak-rule-inject がありません）")
        return 1
    for path in restored:
        shutil.copy2(backup_path(path), path)
        backup_path(path).unlink()
        print(f"{path} の書き戻し: changed")
    if CONFIG_PATH.is_file():
        CONFIG_PATH.unlink()
        print(f"{CONFIG_PATH} の削除: changed")
    else:
        print(f"{CONFIG_PATH} の削除: skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
