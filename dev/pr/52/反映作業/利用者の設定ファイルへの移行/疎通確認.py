"""移行が触る settings.json と ~/.config に、読み取りだけでつながるかを確かめる。"""

from __future__ import annotations

import os
import sys

from _migration import CONFIG_PATH, HOME, MigrationError, read_json, settings_files


def main() -> int:
    """対象ごとに結果の行を出す。"""
    failed = False
    files = settings_files()
    if not files:
        print("settings.json: failed（~/.claude*/settings.json がありません）")
        return 1
    for path in files:
        try:
            read_json(path)
        except MigrationError as error:
            print(f"{path}: failed（{error}）")
            failed = True
            continue
        # 書き換えとバックアップのため、フォルダに書けるかも見る
        if os.access(path.parent, os.W_OK):
            print(f"{path}: ok")
        else:
            print(f"{path}: failed（{path.parent} に書けません）")
            failed = True
    # settings.yaml を作る先の、既にある一番近い親フォルダに書けるか
    parent = next(folder for folder in CONFIG_PATH.parents if folder.exists())
    if parent.is_relative_to(HOME) and os.access(parent, os.W_OK):
        print(f"{parent}: ok")
    else:
        print(f"{parent}: failed（{CONFIG_PATH} を作れません）")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
