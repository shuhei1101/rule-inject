"""PoC のフックを起動から終了まで測り、経路ごとの p50・p99・p99.9 を出す。

応答する経路は、測る間だけ空いているポートで待ち受ける。
起動を依頼する経路は、何もしない有効なユニットへ依頼し、PoC のサーバーを起動しない。
"""

from __future__ import annotations

import json
import os
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path

HOOK = Path(__file__).with_name("start_server.py")
DUMMY_SERVICE = "rule-inject-poc-112-dummy.service"
RUNS = int(os.environ.get("POC_RUNS", "1000"))
PAYLOAD = json.dumps({"session_id": "poc-112", "hook_event_name": "SessionStart", "source": "startup"})


def _free_port() -> int:
    """空いているポートを 1 つ返す。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _measure(port: int) -> list[float]:
    """フックを RUNS 回実行し、各回の秒数を返す。"""
    env = {**os.environ, "RULE_INJECT_PORT": str(port), "RULE_INJECT_POC_SERVICE": DUMMY_SERVICE}
    env.pop("RULE_INJECT_POC_LOG", None)
    durations = []
    for _ in range(RUNS):
        started = time.perf_counter()
        subprocess.run([sys.executable, str(HOOK)], input=PAYLOAD, text=True, env=env, check=True)
        durations.append(time.perf_counter() - started)
    return durations


def _summary(durations: list[float]) -> dict[str, float]:
    """p50・p99・p99.9 と、p99.9 に余裕 50% を加えた値をミリ秒で返す。"""
    cuts = statistics.quantiles(durations, n=1000, method="inclusive")
    p999 = cuts[998]
    return {
        "p50_ms": round(statistics.median(durations) * 1000, 1),
        "p99_ms": round(cuts[989] * 1000, 1),
        "p999_ms": round(p999 * 1000, 1),
        "p999_plus_50pct_ms": round(p999 * 1.5 * 1000, 1),
        "max_ms": round(max(durations) * 1000, 1),
    }


def main() -> None:
    """2 つの経路を測って JSON で出す。"""
    results = {}
    # 応答する経路: 測る間だけ待ち受ける
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1024)
        results["responding"] = _summary(_measure(listener.getsockname()[1]))
    # 応答しない経路: 待ち受けの無いポートで is-enabled と start --no-block まで進む
    results["start_requested"] = _summary(_measure(_free_port()))
    print(json.dumps({"runs": RUNS, **results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
