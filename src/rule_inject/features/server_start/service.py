"""常駐の MCP サーバーの応答の確認と、systemd --user のユニットへの起動の依頼。"""

from __future__ import annotations

import socket
import subprocess

from rule_inject.features.server_start.types import UnitStart
from rule_inject.shared.errors import UnitCheckError, UnitStartError, describe

# サーバーの待ち受けのアドレス（非機能要件「MCPサーバーの待ち受けのアドレス」）
LOOPBACK = "127.0.0.1"
# ポートへ TCP で接続するときの待ちの上限（秒。非機能要件「サーバーの応答の確認の待ち」）
PROBE_TIMEOUT_SECONDS = 0.1
# systemctl --user の 1 回の呼び出しの打ち切り（秒。非機能要件「ユニットの確認と起動の依頼の待ち」）
SYSTEMCTL_TIMEOUT_SECONDS = 0.3


def server_responds(port: int, *, timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
    """`LOOPBACK` のポートへ TCP で接続できるかを返す。"""
    try:
        with socket.create_connection((LOOPBACK, port), timeout=timeout):
            return True
    except OSError:
        # 拒まれた・待ちを過ぎた（TimeoutError は OSError の派生）: 応答しないものとして扱う
        return False


def _systemctl(args: list[str], timeout: float) -> int:
    """`systemctl --user` を入出力を捨てて実行し、終了コードを返す。"""
    completed = subprocess.run(
        ["systemctl", "--user", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )
    return completed.returncode


def request_unit_start(service: str, *, timeout: float = SYSTEMCTL_TIMEOUT_SECONDS) -> UnitStart:
    """ユニットが有効なときだけ `systemctl --user start --no-block` で起動を依頼し、結果を返す。"""
    # 1. ユニットが有効かを確かめる
    try:
        enabled = _systemctl(["is-enabled", "--quiet", "--", service], timeout)
    except FileNotFoundError:
        # systemctl が無い端末: 補助の対象外として何もしない
        return UnitStart.SYSTEMCTL_MISSING
    except subprocess.TimeoutExpired as exc:
        raise UnitCheckError(f"systemctl --user is-enabled {service}", describe(exc)) from exc
    # 有効でない・ユニットが無い・ユーザーの systemd に接続できない: 起動しない
    if enabled != 0:
        return UnitStart.NOT_ENABLED
    # 2. 待ち受けの開始を待たずに起動を依頼する
    try:
        started = _systemctl(["start", "--no-block", "--", service], timeout)
    except subprocess.TimeoutExpired as exc:
        raise UnitStartError(f"systemctl --user start {service}", describe(exc)) from exc
    if started != 0:
        raise UnitStartError(f"systemctl --user start {service}", f"終了コード {started}")
    return UnitStart.REQUESTED
