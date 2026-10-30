"""dev-docs の `search_docs` を順に呼び、接続から応答までの時間を JSON Lines へ 1 回ずつ追記する。

途中で止まっても、結果のファイルの行数から続きを呼ぶ。
"""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from rule_inject.server.dev_docs import SEARCH_DOCS_TOOL, TAG_GROUP_ARGUMENTS

# 手元で常駐している dev-docs の接続先
DEV_DOCS_URL = "http://127.0.0.1:8781/mcp"
# 1 回の呼び出しを打ち切る時間（秒）。応答しない 1 回で測定全体を止めない
CALL_LIMIT_SECONDS = 600
# 既定の呼び出しの回数
DEFAULT_COUNT = 1000


async def _call_once(cwd: str) -> dict:
    """接続からツールの応答までを 1 回測る。"""
    started = time.monotonic()
    try:
        async with asyncio.timeout(CALL_LIMIT_SECONDS):
            async with streamable_http_client(DEV_DOCS_URL) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(SEARCH_DOCS_TOOL, {**TAG_GROUP_ARGUMENTS, "cwd": cwd})
    # 失敗した回も 1 行として残し、集計で数える（測定は続ける）
    except Exception as error:
        return {"seconds": round(time.monotonic() - started, 3), "error": repr(error)}
    elapsed = time.monotonic() - started
    text = "".join(item.text for item in result.content if isinstance(item, TextContent))
    # ツールのエラーは本文が JSON でないため、件数を読まない
    total = None if result.is_error else json.loads(text).get("total_count")
    return {"seconds": round(elapsed, 3), "is_error": result.is_error, "total_count": total}


async def main() -> None:
    """結果のファイルの行数から続けて、指定の回数まで呼ぶ。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True, help="配信元の中の作業場所")
    parser.add_argument("--out", required=True, type=Path, help="結果の JSON Lines")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    args = parser.parse_args()

    done = len(args.out.read_text(encoding="utf-8").splitlines()) if args.out.exists() else 0
    for index in range(done, args.count):
        row = {"index": index, "at": datetime.now(UTC).isoformat(), **await _call_once(args.cwd)}
        with args.out.open("a", encoding="utf-8") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
