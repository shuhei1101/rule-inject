"""PoC のフック。PreToolUse で既読の記録を書き、SessionEnd でそのセッションの記録を消す。

Usage:
python3 poc_hook.py record
python3 poc_hook.py end
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# 結果を置くフォルダを指す環境変数（Claude Code の起動時に渡す）
RESULTS_DIR_ENV = "POC_RESULTS_DIR"
LOG_FILE_NAME = "poc.log.jsonl"
STATE_DIR_NAME = "state"


def _append_log(results_dir: Path, hook: str, payload: dict[str, object], **extra: object) -> None:
    """入力の JSON と時刻を 1 行でログへ追記する。"""
    line = {"time": datetime.now(UTC).isoformat(), "hook": hook, "input": payload, **extra}
    with (results_dir / LOG_FILE_NAME).open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(line, ensure_ascii=False) + "\n")


def main() -> int:
    """引数のフックを動かして 0 を返す。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("hook", choices=["record", "end"])
    args = parser.parse_args()
    payload = json.load(sys.stdin)
    results_dir = Path(os.environ[RESULTS_DIR_ENV])
    state_dir = results_dir / STATE_DIR_NAME
    state_dir.mkdir(parents=True, exist_ok=True)
    record = state_dir / f"{payload['session_id']}.txt"
    # PreToolUse: そのセッションの記録ファイルへ 1 行足す
    if args.hook == "record":
        with record.open("a", encoding="utf-8") as record_file:
            record_file.write(f"{payload.get('tool_name')}\n")
        _append_log(results_dir, args.hook, payload)
        return 0
    # SessionEnd: そのセッションの記録ファイルを消し、消す前にあったかと、残っている記録ファイルを残す
    existed = record.is_file()
    record.unlink(missing_ok=True)
    remaining = sorted(path.name for path in state_dir.glob("*.txt"))
    _append_log(results_dir, args.hook, payload, record_existed=existed, remaining=remaining)
    return 0


if __name__ == "__main__":
    sys.exit(main())
