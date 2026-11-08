"""settings.json の env に旧い RULE_INJECT_* が無く、その値が settings.yaml に入っているかを読むだけで確かめる。

Usage:
# リポジトリの直下で移行の結果を読むだけで確かめる
python3 dev/pr/52/反映作業/利用者の設定ファイルへの移行/確認.py
"""

from __future__ import annotations

import sys

from _migration import (
    CONFIG_ENV,
    CONFIG_PATH,
    ENV_PREFIX,
    MigrationError,
    Target,
    backup_path,
    collect_values,
    missing_values,
    old_env_keys,
    read_existing_global,
    read_json,
    settings_files,
)


def main() -> int:
    """settings.json ごとと settings.yaml の観測した値を出す。"""
    failed = False
    backups: list[Target] = []
    for path in settings_files():
        try:
            data = read_json(path)
        except MigrationError as error:
            print(f"{path}: failed（{error}）")
            failed = True
            continue
        env = data.get("env")
        if not isinstance(env, dict):
            env = {}
        backup = backup_path(path)
        backup_data = read_json(backup) if backup.is_file() else None
        if backup_data is None and not any(key.startswith(ENV_PREFIX) for key in env):
            # バックアップも RULE_INJECT_ のキーも無い設定フォルダは、rule-inject を使っていないため対象外
            continue
        left = old_env_keys(data)
        pointed = env.get(CONFIG_ENV)
        # 既にあった settings.yaml へ移した settings.json は、移行の前後とも RULE_INJECT_CONFIG を持たない
        kept_default = (
            pointed is None
            and backup_data is not None
            and CONFIG_ENV not in (backup_data.get("env") or {})
        )
        if left or not (pointed == str(CONFIG_PATH) or kept_default):
            print(f"{path}: failed（残っているキー {left}、{CONFIG_ENV}={pointed}）")
            failed = True
        else:
            print(f"{path}: ok（{CONFIG_ENV}={pointed}）")
        if backup_data is not None:
            backups.append(Target(path=backup, data=backup_data))
    if not backups:
        print("移行前の値: failed（settings.json.bak-rule-inject がありません）")
        return 1
    # 移行前に持っていた値が、今の settings.yaml の global の対応するキーに入っているかを比べる
    try:
        missing = missing_values(collect_values(backups), read_existing_global())
        actual = CONFIG_PATH.read_text(encoding="utf-8")
    except (OSError, MigrationError) as error:
        print(f"{CONFIG_PATH}: failed（{error}）")
        return 1
    if not missing:
        print(f"{CONFIG_PATH}: ok")
    else:
        print(f"{CONFIG_PATH}: failed（入っていない移行前の値 {missing}）")
        failed = True
    print(actual, end="")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
