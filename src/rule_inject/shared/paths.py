"""既定の記録フォルダ・ログのフォルダとルールの場所の解決。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

# 状態の配置場所を上書きする環境変数
STATE_DIR_ENV = "RULE_INJECT_STATE_DIR"
STATE_DIR_NAME = "rule-inject"
# 既定のログのフォルダの最後の名前（既定の記録フォルダの下）
LOG_DIR_NAME = "logs"
DEFAULT_STATE_HOME = "~/.local/state"


def default_state_dir(env: Mapping[str, str]) -> Path:
    """設定ファイルに `global.state_dir` が無いときの記録フォルダを決める（作らない）。"""
    # 環境変数があれば、その値を配置場所にする
    configured = env.get(STATE_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    # XDG の状態フォルダ（無いか空なら ~/.local/state）の下の既定の名前にする
    state_home = env.get("XDG_STATE_HOME") or DEFAULT_STATE_HOME
    return Path(state_home).expanduser() / STATE_DIR_NAME


def default_log_dir(env: Mapping[str, str]) -> Path:
    """設定ファイルに `global.log_dir` が無いとき・設定ファイルが読めないときのログのフォルダを決める（作らない）。"""
    # 設定ファイルの `global.state_dir` には従わず、既定の記録フォルダの下にする
    return default_state_dir(env) / LOG_DIR_NAME


def resolve_location(location: str, base: Path) -> str:
    """ルールの場所や対象のパスを、照合・記録に使用する正規の形式へ統一する。"""
    # `~` を展開し、相対パスは基準から解く
    expanded = os.path.expanduser(location)
    joined = expanded if os.path.isabs(expanded) else os.path.join(base, expanded)
    # `..` を畳む（シンボリックリンクは辿らない）
    return os.path.normpath(joined)
