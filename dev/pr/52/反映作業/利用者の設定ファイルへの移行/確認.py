"""settings.json の env に旧い RULE_INJECT_* が無く、その値が settings.yaml に入っているかを読むだけで確かめる。"""

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
    old_env_keys,
    read_json,
    render_settings,
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
        if not isinstance(env, dict) or not any(key.startswith(ENV_PREFIX) for key in env):
            # rule-inject を使っていない設定フォルダは対象外
            continue
        left = old_env_keys(data)
        pointed = env.get(CONFIG_ENV)
        if left or pointed != str(CONFIG_PATH):
            print(f"{path}: failed（残っているキー {left}、{CONFIG_ENV}={pointed}）")
            failed = True
        else:
            print(f"{path}: ok（{CONFIG_ENV}={pointed}）")
        backup = backup_path(path)
        if backup.is_file():
            backups.append(Target(path=backup, data=read_json(backup)))
    if not backups:
        print("移行前の値: failed（settings.json.bak-rule-inject がありません）")
        return 1
    # 移行前に持っていた値から作った内容と、今の settings.yaml を比べる
    try:
        expected = render_settings(collect_values(backups))
        actual = CONFIG_PATH.read_text(encoding="utf-8")
    except (OSError, MigrationError) as error:
        print(f"{CONFIG_PATH}: failed（{error}）")
        return 1
    if actual == expected:
        print(f"{CONFIG_PATH}: ok")
    else:
        print(f"{CONFIG_PATH}: failed（移行前の値と一致しません）")
        failed = True
    print(actual, end="")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
