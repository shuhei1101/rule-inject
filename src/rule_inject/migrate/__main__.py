"""設定の移し替えの入口（`python -m rule_inject.migrate`）。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime

from rule_inject.features.migrate.service import apply_migration, plan_migration
from rule_inject.features.migrate.types import SettingsNewerError
from rule_inject.shared.errors import SettingsReadError
from rule_inject.shared.settings import backup_dir, config_path

# 設定がツールより新しいときの終了コード
NEWER_EXIT_CODE = 6
# 設定ファイルが読み取れないときの終了コード
FAILURE_EXIT_CODE = 1


def main() -> None:
    """手順の算出か適用を実行し、結果を JSON で標準出力へ書き込む。"""
    parser = argparse.ArgumentParser(prog="rule_inject.migrate")
    parser.add_argument("--plan", action="store_true", help="手順を示すだけで書き換えない")
    plan_only = parser.parse_args().plan
    env = os.environ
    path = config_path(env)
    try:
        result = (
            plan_migration(path)
            if plan_only
            else apply_migration(path, backup_dir(env), now=datetime.now(UTC))
        )
    except SettingsNewerError as exc:
        print(
            f"設定のバージョン {exc.settings_version} は"
            f"ツールのバージョン {exc.tool_version} より新しい",
            file=sys.stderr,
        )
        sys.exit(NEWER_EXIT_CODE)
    except SettingsReadError as exc:
        print(f"{exc.path}: {exc.reason}", file=sys.stderr)
        sys.exit(FAILURE_EXIT_CODE)
    print(
        json.dumps(
            {
                "from": result.source_version,
                "to": result.target_version,
                "steps": list(result.steps),
                "migrations": list(result.migrations),
                "backup": result.backup,
                "env": result.env,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
