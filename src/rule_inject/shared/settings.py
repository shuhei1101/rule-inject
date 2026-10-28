"""設定ファイルの読み取りと、`projects` の当て方。"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from rule_inject.shared._settings_yaml import parse_settings
from rule_inject.shared.errors import SettingsReadError, describe
from rule_inject.shared.paths import default_log_dir, default_state_dir, resolve_location

# 設定ファイルの場所を指す環境変数
CONFIG_ENV = "RULE_INJECT_CONFIG"
PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
CONFIG_HOME_ENV = "XDG_CONFIG_HOME"
DEFAULT_CONFIG_HOME = "~/.config"
# `global.indexes` が無いときに読む索引の、設定フォルダからのパス
USER_INDEX_DEFAULT = "rule-inject/rules.yaml"
# 当たった `projects` の要素のどれも `indexes` を持たないときに読む索引の、`CLAUDE_PROJECT_DIR` からのパス
PROJECT_INDEX_DEFAULT = "rules.yaml"
# `projects[].match` を当てるとき、この下を本体のリポジトリとして見るフォルダ
WORKTREES_DIR = ".claude/worktrees"
# 設定ファイルに保持日数が無いときの日数
DEFAULT_RECORD_RETENTION_DAYS = 30
DEFAULT_LOG_RETENTION_DAYS = 3
# 10 進の整数の書き方（符号は付けてよい）
INTEGER_PATTERN = re.compile(r"[+-]?[0-9]+")
MIN_RETENTION_DAYS = 1
# MCP サーバーの待ち受けのポートの既定と、許す範囲
DEFAULT_SERVER_PORT = 8783
MIN_SERVER_PORT = 1024
MAX_SERVER_PORT = 65535
# `global.server_port` をその起動だけ上書きする環境変数
PORT_ENV = "RULE_INJECT_PORT"


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    """設定ファイルと既定値から決めた、フックが使う値。"""

    indexes: tuple[str, ...]
    # `indexes` のうち、当たった `projects` の要素の `indexes` とプロジェクトの既定の置き場所から入ったもの（フックは使わない）
    project_indexes: tuple[str, ...]
    state_dir: Path
    log_dir: Path
    record_retention_days: int
    log_retention_days: int
    # MCP サーバーが待ち受けるポート（フックは使わない）
    server_port: int


def _matches_project(match: str, project_dir: str) -> bool:
    """`projects[].match` が起動したプロジェクトに当たるかを返す。"""
    # worktree は本体のパスで見る
    normalized = os.path.normpath(project_dir)
    marker = f"/{WORKTREES_DIR}/"
    base = normalized[: normalized.index(marker)] if marker in normalized else normalized
    expanded = os.path.expanduser(match)
    # 絶対パスは、そのパスかその配下に当てる
    if os.path.isabs(expanded):
        target = os.path.normpath(expanded)
        return base == target or base.startswith(target.rstrip("/") + "/")
    # それ以外はプロジェクト名として、リポジトリのフォルダ名に当てる
    return os.path.basename(base) == match


def _value_error(config: str, key: str, written: str, allowed: str) -> SettingsReadError:
    """値が許す範囲の外のときの SettingsReadError を作る。"""
    return SettingsReadError(path=config, reason=f"{key}: {written} は {allowed}ではない")


def _absolute_path(config: str, key: str, written: str) -> str:
    """`~` を展開した絶対パスを返し、絶対パスでなければ SettingsReadError を送出する。"""
    expanded = os.path.expanduser(written)
    if not os.path.isabs(expanded):
        raise _value_error(config, key, written, "絶対パス")
    return expanded


def _retention_days(config: str, key: str, written: str | None, default: int) -> int:
    """保持日数を 1 以上の整数として読み、無ければ既定の日数を返す。"""
    if written is None:
        return default
    if not INTEGER_PATTERN.fullmatch(written) or int(written) < MIN_RETENTION_DAYS:
        raise _value_error(config, key, written, "1 以上の整数")
    return int(written)


def _server_port(config: str, key: str, written: str) -> int:
    """ポートを許す範囲の整数として読み、範囲の外なら SettingsReadError を送出する。"""
    if (
        not INTEGER_PATTERN.fullmatch(written)
        or not MIN_SERVER_PORT <= int(written) <= MAX_SERVER_PORT
    ):
        raise _value_error(config, key, written, f"{MIN_SERVER_PORT}〜{MAX_SERVER_PORT} の整数")
    return int(written)


def _resolve_server_port(
    config: str, global_values: Mapping[str, object], env: Mapping[str, str]
) -> int:
    """環境変数のポート、無ければ設定ファイルのポート、それも無ければ既定のポートを返す。"""
    from_env = env.get(PORT_ENV)
    # 環境変数が空でなければ、設定ファイルより優先する（誤りの場所は環境変数の名前）
    if from_env:
        return _server_port(PORT_ENV, PORT_ENV, from_env)
    written = global_values.get("server_port")
    if written is None:
        return DEFAULT_SERVER_PORT
    return _server_port(config, "global.server_port", str(written))


def _read_config(env: Mapping[str, str]) -> tuple[str, dict[str, object]]:
    """`RULE_INJECT_CONFIG` が指す設定ファイルを読み、場所と読み取った値を返す。指していなければ空の値を返す。"""
    configured = env.get(CONFIG_ENV)
    if not configured:
        return "", {}
    config = os.path.expanduser(configured)
    try:
        text = Path(config).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SettingsReadError(path=config, reason=describe(exc)) from exc
    try:
        return config, dict(parse_settings(text))
    except ValueError as exc:
        raise SettingsReadError(path=config, reason=describe(exc)) from exc


def _default_user_index(env: Mapping[str, str]) -> list[str]:
    """ユーザーの既定の置き場所の索引を、ファイルがあるときだけ返す。"""
    # 設定フォルダは XDG_CONFIG_HOME（無いか空なら ~/.config）
    config_home = env.get(CONFIG_HOME_ENV) or DEFAULT_CONFIG_HOME
    candidate = Path(config_home).expanduser() / USER_INDEX_DEFAULT
    return [str(candidate)] if candidate.is_file() else []


def load_settings(env: Mapping[str, str]) -> Settings:
    """設定ファイルを読み、当たった `projects` の要素を重ね、既定値で埋めた設定を返す。"""
    config, parsed = _read_config(env)
    global_values = dict(parsed.get("global", {}))
    projects = list(parsed.get("projects", []))
    # 値を確かめる
    for number, project in enumerate(projects):
        if "match" not in project:
            raise SettingsReadError(
                path=config, reason=f"projects[{number}].match: 必須のキーが無い"
            )
    global_indexes = [
        _absolute_path(config, "global.indexes", written)
        for written in global_values.get("indexes", [])
    ]
    state_dir = (
        Path(_absolute_path(config, "global.state_dir", global_values["state_dir"]))
        if "state_dir" in global_values
        else default_state_dir(env)
    )
    log_dir = (
        Path(_absolute_path(config, "global.log_dir", global_values["log_dir"]))
        if "log_dir" in global_values
        else default_log_dir(env)
    )
    record_days = _retention_days(
        config,
        "global.record_retention_days",
        global_values.get("record_retention_days"),
        DEFAULT_RECORD_RETENTION_DAYS,
    )
    log_days = _retention_days(
        config,
        "global.log_retention_days",
        global_values.get("log_retention_days"),
        DEFAULT_LOG_RETENTION_DAYS,
    )
    server_port = _resolve_server_port(config, global_values, env)
    # 起動したプロジェクトの直下に当たる要素を、並びの順に集める
    project_dir = env.get(PROJECT_DIR_ENV)
    matched = (
        [project for project in projects if _matches_project(project["match"], project_dir)]
        if project_dir
        else []
    )
    # 索引の並び: global（無ければユーザーの既定）、続けて当たった要素の indexes
    indexes = global_indexes if "indexes" in global_values else _default_user_index(env)
    project_indexes: list[str] = []
    for project in matched:
        project_indexes.extend(
            resolve_location(written, Path(project_dir)) for written in project.get("indexes", [])
        )
    # 当たった要素のどれも indexes を持たなければ、プロジェクトの既定の置き場所を読む
    if project_dir and not any("indexes" in project for project in matched):
        default_project_index = Path(project_dir) / PROJECT_INDEX_DEFAULT
        if default_project_index.is_file():
            project_indexes.append(str(default_project_index))
    return Settings(
        indexes=(*indexes, *project_indexes),
        project_indexes=tuple(project_indexes),
        state_dir=state_dir,
        log_dir=log_dir,
        record_retention_days=record_days,
        log_retention_days=log_days,
        server_port=server_port,
    )
