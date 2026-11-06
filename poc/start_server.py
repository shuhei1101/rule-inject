"""PoC の SessionStart フック。サーバーが応答しなければ systemd --user のユニットへ起動を依頼する。"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

SERVICE = os.environ.get("RULE_INJECT_POC_SERVICE", "rule-inject-poc-112.service")
# PoC の仮の値。本番の値は非機能要件に導出つきで置く
CONNECT_TIMEOUT_SECONDS = 0.2
SYSTEMCTL_TIMEOUT_SECONDS = 0.5


def _responds(port: int) -> bool:
    """127.0.0.1 のポートへ TCP で接続できるかを返す。"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=CONNECT_TIMEOUT_SECONDS):
            return True
    except OSError:
        return False


def _systemctl(*args: str) -> int:
    """systemctl --user を実行し、終了コードを返す。"""
    completed = subprocess.run(
        ["systemctl", "--user", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=SYSTEMCTL_TIMEOUT_SECONDS,
        check=False,
    )
    return completed.returncode


def main() -> None:
    """応答を確かめ、要るときだけ起動を依頼して、測定の記録を 1 行書く。"""
    started = time.time()
    sys.stdin.read()
    port = int(os.environ.get("RULE_INJECT_PORT", "8783"))
    record: dict[str, object] = {"hook_started": started, "port": port}
    # サーバーが応答するか
    if _responds(port):
        # 応答する: 何も起動しない
        record["path"] = "responding"
    # 応答しない: ユニットが有効か
    elif _systemctl("is-enabled", "--quiet", "--", SERVICE) != 0:
        # 有効でない: 利用者が常駐をやめたとみなして起動しない
        record["path"] = "not_enabled"
    else:
        # 有効: 待ち受けの開始を待たずに起動を依頼する
        record["path"] = "start_requested"
        record["start_exit"] = _systemctl("start", "--no-block", "--", SERVICE)
    record["hook_finished"] = time.time()
    log_path = os.environ.get("RULE_INJECT_POC_LOG")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")


if __name__ == "__main__":
    main()
