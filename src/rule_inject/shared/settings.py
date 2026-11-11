"""設定ファイルの読み取りと、`projects` の当て方。"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from rule_inject.shared._settings_yaml import parse_settings
from rule_inject.shared.errors import SettingsReadError, describe
from rule_inject.shared.paths import (
    STATE_DIR_ENV,
    default_log_dir,
    default_state_dir,
    resolve_location,
)

# 設定ファイルの場所を指す環境変数
CONFIG_ENV = "RULE_INJECT_CONFIG"
PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
CONFIG_HOME_ENV = "XDG_CONFIG_HOME"
DEFAULT_CONFIG_HOME = "~/.config"
# `global.indexes` が無いときに読む索引の、設定フォルダからのパス
USER_INDEX_DEFAULT = "rule-inject/rules.yaml"
# `RULE_INJECT_CONFIG` が無いときに読む設定ファイルの、設定フォルダからのパス
CONFIG_FILE_DEFAULT = "rule-inject/settings.yaml"
# 設定ファイルのバックアップを配置するフォルダの、設定フォルダからのパス
BACKUP_DIR_DEFAULT = "rule-inject/bk"
# 該当した `projects` の要素のどれも `indexes` を持たないときに読む索引の、`CLAUDE_PROJECT_DIR` からのパス
PROJECT_INDEX_DEFAULT = "rules.yaml"
# `projects[].match` を照合するとき、この下を本体のリポジトリとして確認するフォルダ
WORKTREES_DIR = ".claude/worktrees"
# 設定ファイルに保持日数が無いときの日数
DEFAULT_RECORD_RETENTION_DAYS = 30
DEFAULT_LOG_RETENTION_DAYS = 3
# 10 進の整数の記法（符号は付けてよい）
INTEGER_PATTERN = re.compile(r"[+-]?[0-9]+")
MIN_RETENTION_DAYS = 1
# MCP サーバーの待ち受けのポートの既定と、許す範囲
DEFAULT_SERVER_PORT = 8783
MIN_SERVER_PORT = 1024
MAX_SERVER_PORT = 65535
# MCP サーバーのポートを指す環境変数
PORT_ENV = "RULE_INJECT_PORT"
# 設定ファイルに `global.server_service` が無いときの、サーバーを起動するユニットのサービス名
DEFAULT_SERVER_SERVICE = "rule-inject"
# `global.server_service` に許す値（`fullmatch` で照合する）
SERVICE_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
# 設定ファイルに `global.dev_docs_url` が無いときの dev-docs の接続先
DEFAULT_DEV_DOCS_URL = "http://127.0.0.1:8781/mcp"
# `global.dev_docs_url` の先頭に許す文字列
DEV_DOCS_URL_SCHEMES = ("http://", "https://")


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    """設定ファイルと既定値から決めた、フックが使用する値。"""

    indexes: tuple[str, ...]
    # `indexes` のうち、該当した `projects` の要素の `indexes` とプロジェクトの既定の配置場所から入ったもの（フックは使用しない）
    project_indexes: tuple[str, ...]
    state_dir: Path
    log_dir: Path
    record_retention_days: int
    log_retention_days: int
    # MCP サーバーが待ち受けるポート（フックはサーバーの起動の補助だけが使用する）
    server_port: int
    # `check_indexes` が使用中のタグを取得する dev-docs の MCP サーバーの URL（フックは使用しない）
    dev_docs_url: str
    # 応答しない MCP サーバーを起動する systemd --user のユニットのサービス名
    server_service: str


def _matches_project(match: str, project_dir: str) -> bool:
    """`projects[].match` が起動したプロジェクトに該当するかを返却する。"""
    # worktree は本体のパスで確認する
    normalized = os.path.normpath(project_dir)
    marker = f"/{WORKTREES_DIR}/"
    base = normalized[: normalized.index(marker)] if marker in normalized else normalized
    expanded = os.path.expanduser(match)
    # 絶対パスは、そのパスかその配下に照合する
    if os.path.isabs(expanded):
        target = os.path.normpath(expanded)
        return base == target or base.startswith(target.rstrip("/") + "/")
    # それ以外はプロジェクト名として、リポジトリのフォルダ名に照合する
    return os.path.basename(base) == match


def _value_error(config: str, key: str, written: str, allowed: str) -> SettingsReadError:
    """値が許す範囲の外のときの SettingsReadError を作る。"""
    return SettingsReadError(path=config, reason=f"{key}: {written} は {allowed}ではない")


def _absolute_path(config: str, key: str, written: str) -> str:
    """`~` を展開した絶対パスを返却し、絶対パスでなければ SettingsReadError を送出する。"""
    expanded = os.path.expanduser(written)
    if not os.path.isabs(expanded):
        raise _value_error(config, key, written, "絶対パス")
    return expanded


def _retention_days(config: str, key: str, written: str | None, default: int) -> int:
    """保持日数を 1 以上の整数として読み、無ければ既定の日数を返却する。"""
    if written is None:
        return default
    if not INTEGER_PATTERN.fullmatch(written) or int(written) < MIN_RETENTION_DAYS:
        raise _value_error(config, key, written, "1 以上の整数")
    return int(written)


def _resolve_server_port(env: Mapping[str, str]) -> int:
    """環境変数のポート、無ければ既定のポートを返却する。"""
    written = env.get(PORT_ENV)
    if not written:
        return DEFAULT_SERVER_PORT
    # 許す範囲の外は、環境変数の名前を場所にした誤りにする
    if (
        not INTEGER_PATTERN.fullmatch(written)
        or not MIN_SERVER_PORT <= int(written) <= MAX_SERVER_PORT
    ):
        raise _value_error(
            PORT_ENV, PORT_ENV, written, f"{MIN_SERVER_PORT}〜{MAX_SERVER_PORT} の整数"
        )
    return int(written)


def _resolve_dev_docs_url(config: str, global_values: Mapping[str, object]) -> str:
    """設定ファイルの dev-docs の接続先、無ければ既定の接続先を返却する。"""
    written = global_values.get("dev_docs_url")
    if written is None:
        return DEFAULT_DEV_DOCS_URL
    url = str(written)
    # http か https で始まらない接続先は設定ファイルの誤り
    if not url.startswith(DEV_DOCS_URL_SCHEMES):
        raise _value_error(config, "global.dev_docs_url", url, "http か https で始まる URL")
    return url


def _resolve_server_service(config: str, global_values: Mapping[str, object]) -> str:
    """設定ファイルのサービス名、無ければ既定のサービス名を返却する。"""
    written = global_values.get("server_service")
    if written is None:
        return DEFAULT_SERVER_SERVICE
    service = str(written)
    # systemctl の引数に引き渡すため、英数字・`_`・`-` の 1〜64 文字だけを許す
    if not SERVICE_NAME_PATTERN.fullmatch(service):
        raise _value_error(config, "global.server_service", service, "1〜64 文字の英数字・_・-")
    return service


def _config_home(env: Mapping[str, str]) -> Path:
    """設定フォルダ（`XDG_CONFIG_HOME`。無いか空なら ~/.config）を返却する。"""
    return Path(env.get(CONFIG_HOME_ENV) or DEFAULT_CONFIG_HOME).expanduser()


def config_path(env: Mapping[str, str]) -> Path:
    """`RULE_INJECT_CONFIG` の値か、無ければ既定のパスを返却する。"""
    configured = env.get(CONFIG_ENV)
    if configured:
        return Path(configured).expanduser()
    return _config_home(env) / CONFIG_FILE_DEFAULT


def backup_dir(env: Mapping[str, str]) -> Path:
    """設定ファイルのバックアップを配置するフォルダを返却する。"""
    return _config_home(env) / BACKUP_DIR_DEFAULT


def _read_config(env: Mapping[str, str]) -> tuple[str, dict[str, object]]:
    """設定ファイルを読み、場所と読み取った値を返却する。既定のパスにファイルが無ければ空の値を返却する。"""
    path = config_path(env)
    # 環境変数で指していないとき、既定のパスのファイルは無くてよい
    if not env.get(CONFIG_ENV) and not path.is_file():
        return "", {}
    config = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SettingsReadError(path=config, reason=describe(exc)) from exc
    try:
        return config, dict(parse_settings(text))
    except ValueError as exc:
        raise SettingsReadError(path=config, reason=describe(exc)) from exc


def _default_user_index(env: Mapping[str, str]) -> list[str]:
    """ユーザーの既定の配置場所の索引を、ファイルがあるときだけ返却する。"""
    candidate = _config_home(env) / USER_INDEX_DEFAULT
    return [str(candidate)] if candidate.is_file() else []


def load_settings(env: Mapping[str, str]) -> Settings:
    """設定ファイルを読み、該当した `projects` の要素を重ね、既定値で埋めた設定を返却する。"""
    config, parsed = _read_config(env)
    global_table = parsed.get("global", {})
    global_values = dict(global_table) if isinstance(global_table, dict) else {}
    project_tables = parsed.get("projects", [])
    projects = list(project_tables) if isinstance(project_tables, list) else []
    # 値を確認する
    for number, project in enumerate(projects):
        if "match" not in project:
            raise SettingsReadError(
                path=config, reason=f"projects[{number}].match: 必須のキーが無い"
            )
    global_indexes = [
        _absolute_path(config, "global.indexes", written)
        for written in global_values.get("indexes", [])
    ]
    # 環境変数の状態の配置場所は、設定ファイルより優先する
    state_dir = (
        Path(_absolute_path(config, "global.state_dir", global_values["state_dir"]))
        if "state_dir" in global_values and not env.get(STATE_DIR_ENV)
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
    server_port = _resolve_server_port(env)
    dev_docs_url = _resolve_dev_docs_url(config, global_values)
    server_service = _resolve_server_service(config, global_values)
    # 起動したプロジェクトの直下に該当する要素を、並びの順に集める
    project_dir = env.get(PROJECT_DIR_ENV)
    matched = (
        [project for project in projects if _matches_project(project["match"], project_dir)]
        if project_dir
        else []
    )
    # 索引の並び: global（無ければユーザーの既定）、続けて該当した要素の indexes
    indexes = global_indexes if "indexes" in global_values else _default_user_index(env)
    project_indexes: list[str] = []
    if project_dir:
        for project in matched:
            project_indexes.extend(
                resolve_location(written, Path(project_dir))
                for written in project.get("indexes", [])
            )
        # 該当した要素のどれも indexes を持たなければ、プロジェクトの既定の配置場所を読む
        if not any("indexes" in project for project in matched):
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
        dev_docs_url=dev_docs_url,
        server_service=server_service,
    )
