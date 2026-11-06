"""サーバーの起動の補助が使う型。"""

from __future__ import annotations

from enum import StrEnum


class UnitStart(StrEnum):
    """`request_unit_start` が返す、起動を依頼したか・依頼しなかった理由。"""

    # `start --no-block` が終了コード 0 で終わった
    REQUESTED = "requested"
    # `is-enabled` が 0 以外（有効でない・ユニットが無い・ユーザーの systemd に接続できない）
    NOT_ENABLED = "not_enabled"
    # `systemctl` が PATH に無い
    SYSTEMCTL_MISSING = "systemctl_missing"
