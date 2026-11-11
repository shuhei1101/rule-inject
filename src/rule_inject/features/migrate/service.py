"""端末の設定ファイルの手順の算出と適用。"""

from __future__ import annotations

import importlib.metadata
import shutil
from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from rule_inject.features.migrate.migrations import v0_2_3
from rule_inject.features.migrate.types import MigrationResult, SettingsNewerError
from rule_inject.shared.errors import SettingsReadError, describe

PACKAGE_NAME = "rule-inject"
VERSION_KEY = "version"
BACKUP_NAME_FORMAT = "settings.%Y%m%d%H%M%S.yaml"
# バージョンの古い順の手順
MIGRATIONS = (v0_2_3,)


def _tool_version() -> str:
    """動いているツールのバージョンを返却する。"""
    return importlib.metadata.version(PACKAGE_NAME)


def _version_key(path: Path, version: str) -> tuple[int, ...]:
    """バージョンを比べられる並びにする。"""
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        raise SettingsReadError(path=str(path), reason=f"version: {version}") from exc


def _load(path: Path) -> tuple[YAML, CommentedMap]:
    """コメントを残して書き込めるように設定ファイルを読み取る。"""
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        data = yaml.load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, YAMLError) as exc:
        raise SettingsReadError(path=str(path), reason=describe(exc)) from exc
    return yaml, data if data is not None else CommentedMap()


def _steps(path: Path, data: CommentedMap) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """適用する手順の説明と、そのうち `version` の更新を除いた移し替えの手順を並べる。"""
    version = data.get(VERSION_KEY)
    tool_version = _tool_version()
    # 設定のほうが新しければ、手順を求めずに止める
    if version is not None and _version_key(path, str(version)) > _version_key(path, tool_version):
        raise SettingsNewerError(settings_version=str(version), tool_version=tool_version)
    migrations = tuple(step.DESCRIPTION for step in MIGRATIONS if step.applies(data))
    # 手順の有無によらず、古いバージョンは更新する
    if str(version) != tool_version:
        return (*migrations, f"version を {tool_version} にする"), migrations
    return migrations, migrations


def plan_migration(path: Path) -> MigrationResult:
    """設定ファイルに適用する手順を求め、書き換えずに返却する。"""
    tool_version = _tool_version()
    if not path.is_file():
        return MigrationResult(
            source_version=None, target_version=tool_version, steps=(), backup=None, env={}
        )
    _, data = _load(path)
    version = data.get(VERSION_KEY)
    steps, migrations = _steps(path, data)
    return MigrationResult(
        source_version=None if version is None else str(version),
        target_version=tool_version,
        steps=steps,
        migrations=migrations,
        backup=None,
        env={},
    )


def apply_migration(path: Path, backup_dir: Path, *, now: datetime) -> MigrationResult:
    """バックアップを作成して手順を適用し、設定ファイルを書き換える。"""
    plan = plan_migration(path)
    if not plan.steps:
        return plan
    # 書き換える前の内容を残す
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / now.strftime(BACKUP_NAME_FORMAT)
    shutil.copyfile(path, backup)
    yaml, data = _load(path)
    env: dict[str, str] = {}
    for step in MIGRATIONS:
        if step.applies(data):
            env.update(step.apply(data))
    # 既にあれば値を変え、無ければ先頭へ追加する
    if VERSION_KEY in data:
        data[VERSION_KEY] = plan.target_version
    else:
        data.insert(0, VERSION_KEY, plan.target_version)
    with path.open("w", encoding="utf-8") as stream:
        yaml.dump(data, stream)
    return MigrationResult(
        source_version=plan.source_version,
        target_version=plan.target_version,
        steps=plan.steps,
        migrations=plan.migrations,
        backup=str(backup),
        env=env,
    )
