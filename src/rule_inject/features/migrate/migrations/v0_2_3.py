"""`global.server_port` を環境変数 `RULE_INJECT_PORT` へ移す手順。"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from rule_inject.shared.settings import DEFAULT_SERVER_PORT, PORT_ENV

DESCRIPTION = "global.server_port を削除し、env の RULE_INJECT_PORT へ移す"
GLOBAL_KEY = "global"
PORT_KEY = "server_port"
# `.mcp.json` の既定と同じポートは `env` へ移さない
DEFAULT_PORT_TEXT = str(DEFAULT_SERVER_PORT)


def applies(data: MutableMapping[str, Any]) -> bool:
    """`global.server_port` を持つかを返す。"""
    return PORT_KEY in (data.get(GLOBAL_KEY) or {})


def apply(data: MutableMapping[str, Any]) -> dict[str, str]:
    """`global.server_port` を削除し、`env` へ移す値を返す。"""
    port = str(data[GLOBAL_KEY].pop(PORT_KEY))
    # 既定のポートは `env` が無くても同じ接続先になる
    if port == DEFAULT_PORT_TEXT:
        return {}
    return {PORT_ENV: port}
