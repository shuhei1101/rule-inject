"""記録フォルダとルールの場所の解決。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

STATE_DIR_NAME = "rule-inject"
STATE_DIR_ENV = "RULE_INJECT_STATE_DIR"
DEFAULT_STATE_HOME = "~/.local/state"
URL_SCHEMES = ("http://", "https://")


def state_dir(env: Mapping[str, str]) -> Path:
    """環境変数から既読の記録とログを置くフォルダを決める（作らない）。"""
    # 記録フォルダを直接指す環境変数があればそれを使う
    configured = env.get(STATE_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    # 無ければ XDG の状態フォルダの下の既定の名前にする
    state_home = env.get("XDG_STATE_HOME") or DEFAULT_STATE_HOME
    return Path(state_home).expanduser() / STATE_DIR_NAME


def resolve_location(location: str, base: Path) -> str:
    """ルールの場所や対象のパスを、照合・記録に使う正規の形へ揃える。"""
    # URL は書かれたまま扱う
    if location.startswith(URL_SCHEMES):
        return location
    # `~` を展開し、相対パスは基準から解く
    expanded = os.path.expanduser(location)
    joined = expanded if os.path.isabs(expanded) else os.path.join(base, expanded)
    # `..` を畳む（シンボリックリンクは辿らない）
    return os.path.normpath(joined)
