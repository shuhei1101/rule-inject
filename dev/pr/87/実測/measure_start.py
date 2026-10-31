"""サーバーを子プロセスで起動し、標準エラーに待ち受けの開始の行が出るまでの秒数を測る。

使い方: uv run python dev/pr/87/実測/measure_start.py {回数} {結果の JSONL}
結合テストの conftest と同じ起動の仕方（`python -m rule_inject.server`・`RULE_INJECT_PORT`）で測る。
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOST = "127.0.0.1"
LIMIT_SEC = 600


def measure_once(work: Path, index: int) -> dict[str, object]:
    """1 回起動して待ち受けの開始の行が出るまでの秒数を返す。"""
    with socket.create_server((HOST, 0)) as probe:
        port = int(probe.getsockname()[1])
    config = work / f"settings-{index}.yaml"
    config.write_text(f"global:\n  server_port: {port}\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("RULE_INJECT_")}
    env.update(
        RULE_INJECT_CONFIG=str(config),
        RULE_INJECT_PORT=str(port),
        XDG_STATE_HOME=str(work / "state"),
        XDG_CONFIG_HOME=str(work / "config"),
    )
    stderr_path = work / f"server-{index}.stderr"
    ready = f"Uvicorn running on http://{HOST}:{port}"
    started = time.monotonic()
    with stderr_path.open("wb") as stderr_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "rule_inject.server"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )
    result: dict[str, object] = {"index": index, "port": port}
    while True:
        elapsed = time.monotonic() - started
        if ready in stderr_path.read_text(encoding="utf-8", errors="replace"):
            result.update(outcome="ready", seconds=round(elapsed, 3))
            break
        if process.poll() is not None:
            result.update(outcome="exited", seconds=round(elapsed, 3))
            break
        if elapsed > LIMIT_SEC:
            result.update(outcome="timeout", seconds=round(elapsed, 3))
            break
        time.sleep(0.05)
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    result["load1"] = os.getloadavg()[0]
    return result


def main() -> None:
    """回数ぶん順に測り、1 回ごとに JSONL へ書く。"""
    count, out = int(sys.argv[1]), Path(sys.argv[2])
    with tempfile.TemporaryDirectory() as tmp, out.open("a", encoding="utf-8") as sink:
        for index in range(count):
            sink.write(json.dumps(measure_once(Path(tmp), index)) + "\n")
            sink.flush()


if __name__ == "__main__":
    main()
