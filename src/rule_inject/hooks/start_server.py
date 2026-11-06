"""サーバーの起動の補助（SessionStart）。応答しない MCP サーバーのユニットへ起動を依頼する。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rule_inject.features.guidance import build_server_start_notice
from rule_inject.features.record import is_valid_session_id
from rule_inject.features.server_start import UnitStart, request_unit_start, server_responds
from rule_inject.hooks._runner import log_settings_failure
from rule_inject.shared.errors import SettingsReadError, UnitCheckError, UnitStartError
from rule_inject.shared.logger import Component, LogOperation, write_log
from rule_inject.shared.settings import load_settings


def start_server(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any] | None:
    """サーバーが応答せずユニットが有効なときだけ起動を依頼し、`/mcp` で接続し直す案内を返す。"""
    # 1. ログに載せるセッション（形式が外れていても補助は行う）
    written = payload.get("session_id")
    session_id = written if is_valid_session_id(written) else None
    # 2. 設定を読む。読めなければ既定のログのフォルダへ書いて何もしない
    try:
        settings = load_settings(env)
    except SettingsReadError as exc:
        log_settings_failure(Component.START_SERVER, exc, env, session_id)
        return None
    # 3. サーバーが応答すれば何もしない
    if server_responds(settings.server_port):
        return None
    # 4. ユニットへ起動を依頼する。失敗はログへ書いて何もしない
    try:
        result = request_unit_start(settings.server_service)
    except UnitCheckError as exc:
        write_log(
            settings.log_dir,
            component=Component.START_SERVER,
            operation=LogOperation.CHECK_UNIT,
            reason=exc.reason,
            session_id=session_id,
            path=exc.path,
        )
        return None
    except UnitStartError as exc:
        write_log(
            settings.log_dir,
            component=Component.START_SERVER,
            operation=LogOperation.START_UNIT,
            reason=exc.reason,
            session_id=session_id,
            path=exc.path,
        )
        return None
    # 5. 起動を依頼したときだけ、接続し直す案内を返す（有効でない・systemctl が無いときは何もしない）
    if result is UnitStart.REQUESTED:
        return {"additionalContext": build_server_start_notice(settings.server_service)}
    return None
