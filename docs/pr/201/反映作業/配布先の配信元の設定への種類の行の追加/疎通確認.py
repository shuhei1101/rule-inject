"""配布先のリポジトリと配信元の設定を、読み取りだけで確かめる。

使い方: python -B 疎通確認.py [対象のリポジトリ]
"""

import sys
from pathlib import Path

import yaml

CONFIG_NAMES = ("project-index.yaml", "dev-docs.yaml")
# 引数の数の上限（スクリプト名と対象のリポジトリ）
MAX_ARGV = 2


def main():
    if len(sys.argv) > MAX_ARGV:
        print("前提確認: failed")
        sys.exit(1)
    root = Path(sys.argv[1] if len(sys.argv) == MAX_ARGV else ".").resolve()
    if not (root / ".git").exists():
        print("対象のリポジトリ: failed")
        sys.exit(1)
    print("対象のリポジトリ: ok")
    config = next((root / n for n in CONFIG_NAMES if (root / n).is_file()), None)
    if config is None:
        print("配信元の設定: failed")
        sys.exit(1)
    try:
        yaml.safe_load(config.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        print("配信元の設定: failed")
        print(err)
        sys.exit(1)
    print(f"配信元の設定: ok（{config.name}）")


if __name__ == "__main__":
    main()
