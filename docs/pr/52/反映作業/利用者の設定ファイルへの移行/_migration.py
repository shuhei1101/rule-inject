"""利用者の設定ファイルへの移行で、疎通確認・実行・確認・切り戻しが共有する対象と変換。"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 既にある settings.yaml は、プラグインの設定ファイルの読み取りで読む（リポジトリの直下の src）
REPO_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO_ROOT / "src"))
from rule_inject.shared._settings_yaml import parse_settings  # noqa: E402

HOME = Path.home()
CONFIG_PATH = HOME / ".config" / "rule-inject" / "settings.yaml"
BACKUP_SUFFIX = ".bak-rule-inject"
CONFIG_ENV = "RULE_INJECT_CONFIG"
ENV_PREFIX = "RULE_INJECT_"
# global に対応するキーが無く、移すと意味が変わる環境変数
UNSUPPORTED_ENV = "RULE_INJECT_INDEXES_PROJECT"
# 環境変数 → settings.yaml の global のキー
ENV_TO_KEY = {
    "RULE_INJECT_INDEXES_USER": "indexes",
    "RULE_INJECT_STATE_DIR": "state_dir",
    "RULE_INJECT_LOG_DIR": "log_dir",
    "RULE_INJECT_RECORD_RETENTION_DAYS": "record_retention_days",
    "RULE_INJECT_LOG_RETENTION_DAYS": "log_retention_days",
}
LIST_KEYS = ("indexes",)
INTEGER_KEYS = ("record_retention_days", "log_retention_days")
MIN_RETENTION_DAYS = 1


class MigrationError(Exception):
    """手順を続けられない状態。"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    """書き換える settings.json 1 つ（シンボリックリンクは実体へ寄せる）。"""

    path: Path
    # JSON をそのまま読んだ内容のため Any
    data: dict[str, Any]


def settings_files() -> list[Path]:
    """`~/.claude/settings.json` と `~/.claude-*/settings.json` の実体を、重複を除いて返す。"""
    found = [HOME / ".claude" / "settings.json", *sorted(HOME.glob(".claude-*/settings.json"))]
    real: dict[Path, None] = {}
    for path in found:
        if path.is_file():
            real.setdefault(path.resolve(), None)
    return list(real)


def read_json(path: Path) -> dict[str, Any]:
    """settings.json を読む。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise MigrationError(f"{path} を読めません: {error}") from error
    if not isinstance(data, dict):
        raise MigrationError(f"{path} の最上位がオブジェクトではありません")
    return data


def old_env_keys(data: dict[str, Any]) -> list[str]:
    """env のうち移す対象の `RULE_INJECT_` のキー（`RULE_INJECT_CONFIG` を除く）を返す。"""
    env = data.get("env")
    if not isinstance(env, dict):
        return []
    return [key for key in env if key.startswith(ENV_PREFIX) and key != CONFIG_ENV]


def list_targets() -> list[Target]:
    """移す対象の環境変数を持つ settings.json を返す。"""
    targets: list[Target] = []
    for path in settings_files():
        data = read_json(path)
        if old_env_keys(data):
            targets.append(Target(path=path, data=data))
    return targets


def collect_values(targets: list[Target]) -> dict[str, str]:
    """対象の環境変数の値を集め、ファイルの間で食い違えば止める。"""
    values: dict[str, str] = {}
    for target in targets:
        env = target.data["env"]
        for key in old_env_keys(target.data):
            # global に対応するキーの無い環境変数は移せない
            if key == UNSUPPORTED_ENV or key not in ENV_TO_KEY:
                raise MigrationError(
                    f"{target.path} の {key} は settings.yaml の global に移せません"
                )
            value = str(env[key])
            if key in values and values[key] != value:
                raise MigrationError(f"{key} の値がファイルの間で食い違っています")
            values[key] = value
    return values


def _quote(value: str) -> str:
    """YAML の二重引用符の文字列にする。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_settings(values: dict[str, str]) -> str:
    """集めた値から settings.yaml の内容を作る（キーの並びは ENV_TO_KEY の順）。"""
    lines = ["global:"]
    for env_key, key in ENV_TO_KEY.items():
        if env_key not in values:
            continue
        value = values[env_key]
        if key in LIST_KEYS:
            # カンマ区切りの環境変数をブロックのリストにする（要素が無ければ空のリスト）
            items = [item.strip() for item in value.split(",") if item.strip()]
            if not items:
                lines.append(f"  {key}: []")
                continue
            lines.append(f"  {key}:")
            lines.extend(f"    - {_quote(item)}" for item in items)
        elif key in INTEGER_KEYS:
            # 保持日数は 1 以上の整数として書く（settings.yaml は 1 未満を誤りとして拒む）
            if not value.strip().isdigit() or int(value) < MIN_RETENTION_DAYS:
                raise MigrationError(f"{env_key} の値 {value} が 1 以上の整数ではありません")
            lines.append(f"  {key}: {int(value)}")
        else:
            lines.append(f"  {key}: {_quote(value)}")
    return "\n".join(lines) + "\n"


def migrated(data: dict[str, Any], *, add_config: bool = True) -> dict[str, Any]:
    """env から移す対象のキーを除き、`add_config` なら `RULE_INJECT_CONFIG` を入れた settings.json の内容を返す。"""
    removed = set(old_env_keys(data))
    env = {key: value for key, value in data["env"].items() if key not in removed}
    if add_config:
        env[CONFIG_ENV] = str(CONFIG_PATH)
    return {**data, "env": env}


def read_existing_global() -> dict[str, str | list[str]]:
    """既にある settings.yaml の `global` を読む（`global` が無ければ空）。"""
    try:
        settings = parse_settings(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise MigrationError(f"{CONFIG_PATH} を読めません: {error}") from error
    table = settings.get("global", {})
    # parse_settings は global をマップで返す。型の絞り込みのために確かめる
    if not isinstance(table, dict):
        raise MigrationError(f"{CONFIG_PATH} の global がマップではありません")
    return table


def missing_values(values: dict[str, str], table: dict[str, str | list[str]]) -> list[str]:
    """env の値のうち、settings.yaml の global の対応するキーに入っていないものを `キー=値` で返す。"""
    missing: list[str] = []
    for env_key, value in values.items():
        key = ENV_TO_KEY[env_key]
        current = table.get(key)
        if key in LIST_KEYS:
            # リストは、カンマ区切りの要素が全て global のリストに含まれていればよい
            present = current if isinstance(current, list) else []
            missing.extend(
                f"{env_key}={item}"
                for item in (part.strip() for part in value.split(","))
                if item and item not in present
            )
        elif key in INTEGER_KEYS:
            # 保持日数は整数として比べる（YAML の表記の違いを吸収する）
            matched = (
                isinstance(current, str)
                and current.strip().isdigit()
                and value.strip().isdigit()
                and int(current) == int(value)
            )
            if not matched:
                missing.append(f"{env_key}={value}")
        elif current != value:
            # 文字列は完全に一致すればよい
            missing.append(f"{env_key}={value}")
    return missing


def render_json(data: dict[str, Any]) -> str:
    """settings.json の書式（インデント 2・非 ASCII はそのまま・末尾に改行）で書き出す。"""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def backup_path(path: Path) -> Path:
    """settings.json のバックアップの置き場所を返す。"""
    return path.with_name(path.name + BACKUP_SUFFIX)
