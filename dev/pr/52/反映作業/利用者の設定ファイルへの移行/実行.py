"""settings.json の env の RULE_INJECT_* を ~/.config/rule-inject/settings.yaml へ移す（--dry-run で計画まで）。

Usage:
# リポジトリの直下で流す（--dry-run で計画まで）
python3 dev/pr/52/反映作業/利用者の設定ファイルへの移行/実行.py [--dry-run]
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from _migration import (
    CONFIG_ENV,
    CONFIG_PATH,
    MigrationError,
    Target,
    backup_path,
    collect_values,
    list_targets,
    migrated,
    read_json,
    render_json,
    render_settings,
    settings_files,
)

CONFIG_STEP = "settings.yaml の作成"


def _already_migrated() -> bool:
    """settings.yaml があり、settings.json のどれかが RULE_INJECT_CONFIG でそれを指しているか。"""
    if not CONFIG_PATH.is_file():
        return False
    pointed = [read_json(path).get("env", {}).get(CONFIG_ENV) for path in settings_files()]
    return str(CONFIG_PATH) in pointed


def _diff(before: str, after: str, before_name: str, after_name: str) -> str:
    """見出しを対象のパスにした unified diff を返す。"""
    lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=before_name,
        tofile=after_name,
    )
    return "".join(lines)


def _write_verified(path: Path, content: str, verify: str) -> None:
    """同じフォルダの一時ファイルに書き、読み直して検証してから置き換える。"""
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        # 検証に通らなければ元のファイルに触れずに止める
        if temp.read_text(encoding="utf-8") != verify:
            raise MigrationError(f"{path} の一時ファイルの内容が計画と一致しません")
        # 書き換えるファイルは元の権限を引き継ぐ
        if path.exists():
            shutil.copymode(path, temp)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _check_prerequisites(targets: list[Target], settings_text: str) -> None:
    """既存の settings.yaml・バックアップと計画が食い違っていれば止める。"""
    # 利用者が置いた別の内容の settings.yaml は上書きしない
    if CONFIG_PATH.exists() and CONFIG_PATH.read_text(encoding="utf-8") != settings_text:
        raise MigrationError(f"{CONFIG_PATH} が既にあり、移す内容と異なります")
    for target in targets:
        # 前のバックアップを上書きすると元に戻せなくなる
        if backup_path(target.path).exists():
            raise MigrationError(f"{backup_path(target.path)} が既にあります")


def _apply_settings(settings_text: str) -> None:
    """settings.yaml を作る。"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_verified(CONFIG_PATH, settings_text, settings_text)


def _apply_target(target: Target, original: str, new_text: str) -> None:
    """settings.json をバックアップしてから書き換える。"""
    if json.loads(new_text) != migrated(target.data):
        raise MigrationError(f"{target.path} の新しい内容が JSON として計画と一致しません")
    backup = backup_path(target.path)
    shutil.copy2(target.path, backup)
    # バックアップから戻せることを確かめる
    if backup.read_text(encoding="utf-8") != original:
        raise MigrationError(f"{backup} の内容が元のファイルと一致しません")
    _write_verified(target.path, new_text, new_text)


def main() -> int:
    """前提確認 → 計画 → 適用の順に流し、手順ごとの結果を出す。"""
    parser = argparse.ArgumentParser(description="利用者の設定ファイルへの移行")
    parser.add_argument("--dry-run", action="store_true", help="計画まで進んで止める")
    dry_run = parser.parse_args().dry_run

    # 前提確認
    try:
        targets = list_targets()
        if not targets:
            # 対象が無いのは、移行済みなら何もしない、そうでなければ想定外として止める
            if _already_migrated():
                print("前提確認: ok")
                print(f"{CONFIG_STEP}: skipped")
                return 0
            raise MigrationError("RULE_INJECT_ の環境変数を持つ settings.json がありません")
        settings_text = render_settings(collect_values(targets))
        _check_prerequisites(targets, settings_text)
    except MigrationError as error:
        print(f"前提確認: failed（{error}）")
        return 1
    print("前提確認: ok")

    # 計画（--dry-run もここを通る）
    config_exists = CONFIG_PATH.exists()
    if not config_exists:
        print(_diff("", settings_text, "/dev/null", str(CONFIG_PATH)), end="")
    plans: list[tuple[Target, str, str]] = []
    for target in targets:
        original = target.path.read_text(encoding="utf-8")
        new_text = render_json(migrated(target.data))
        print(_diff(original, new_text, str(target.path), str(target.path)), end="")
        plans.append((target, original, new_text))
    if dry_run:
        print(f"{CONFIG_STEP}: {'skipped' if config_exists else 'changed'}")
        for target, _, _ in plans:
            print(f"{target.path} の書き換え: changed")
        return 0

    # 適用（settings.yaml を先に作り、settings.json が指す先を用意してから書き換える）
    try:
        if config_exists:
            print(f"{CONFIG_STEP}: skipped")
        else:
            _apply_settings(settings_text)
            print(f"{CONFIG_STEP}: changed")
    except (OSError, MigrationError) as error:
        print(f"{CONFIG_STEP}: failed（{error}）")
        return 1
    for target, original, new_text in plans:
        try:
            _apply_target(target, original, new_text)
        except (OSError, MigrationError) as error:
            print(f"{target.path} の書き換え: failed（{error}）")
            return 1
        print(f"{target.path} の書き換え: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
