"""`check_indexes` を順に呼び、内側の待ち以外の処理の時間を JSON Lines へ 1 回ずつ追記する。

内側の待ち以外の処理の時間は、1 回の呼び出しの全体の時間から、ファイルを辿る時間を引いた残り。
dev-docs への問い合わせは、使われているタグが 0 件の応答をすぐ返す偽の関数に差し替える（区間の中の待ちを測らず、全てのパターンが使われていない最も重い照合にする）。
途中で止まっても、結果のファイルの行数から続きを呼ぶ。
"""

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from rule_inject.features.index.check import load_validator
from rule_inject.server import app, check_tools
from rule_inject.server.dev_docs import UsedTags

# 既定の呼び出しの回数
DEFAULT_COUNT = 1000

# 1 回の呼び出しの中でファイルを辿った時間（秒）
_scan_seconds: list[float] = []
_original_scan = check_tools.scan_unmatched


def _timed_scan(*args, **kwargs):
    """ファイルを辿る時間を測って `_scan_seconds` に残す。"""
    started = time.perf_counter()
    try:
        return _original_scan(*args, **kwargs)
    finally:
        _scan_seconds.append(time.perf_counter() - started)


async def _no_used_tags(url: str, project_dir: str, *, timeout: float) -> UsedTags:  # noqa: ASYNC109 -- 差し替える関数と同じ引数で受ける
    """使われているタグが 0 件の応答をすぐ返す。"""
    return UsedTags(tags=(), reason=None)


async def _call_once(project_dir: str, validator) -> dict:
    """1 回呼び、全体・辿る・残りの時間を返す。"""
    _scan_seconds.clear()
    started = time.perf_counter()
    result = await check_tools.check_indexes(
        project_dir=project_dir,
        env=os.environ,
        validator=validator,
        scan_time_limit=app.UNMATCHED_SCAN_TIME_LIMIT,
        dev_docs_timeout=app.DEV_DOCS_TIMEOUT,
    )
    total = time.perf_counter() - started
    scan = sum(_scan_seconds)
    return {
        "total_seconds": round(total, 4),
        "scan_seconds": round(scan, 4),
        "other_seconds": round(total - scan, 4),
        "is_error": result.is_error,
    }


async def main() -> None:
    """結果のファイルの行数から続けて、指定の回数まで呼ぶ。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True, help="check_indexes の project_dir")
    parser.add_argument("--out", required=True, type=Path, help="結果の JSON Lines")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    args = parser.parse_args()

    check_tools.scan_unmatched = _timed_scan
    check_tools.fetch_used_tags = _no_used_tags
    # サーバーと同じく、検証器は起動時に 1 回だけ作る
    validator = load_validator()
    done = len(args.out.read_text(encoding="utf-8").splitlines()) if args.out.exists() else 0
    for index in range(done, args.count):
        row = {
            "index": index,
            "at": datetime.now(UTC).isoformat(),
            **await _call_once(args.project_dir, validator),
        }
        with args.out.open("a", encoding="utf-8") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
