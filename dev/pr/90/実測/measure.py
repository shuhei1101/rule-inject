"""`check_indexes` を順に呼び、内側の待ち以外の処理の時間を JSON Lines へ 1 回ずつ追記する。

内側の待ち以外の処理の時間は、1 回の呼び出しの全体の時間から、ファイルを辿る時間を引いた残り。
dev-docs への問い合わせは、どのタグのパターンにも当たらないタグを `--tag-count` 件すぐ返す偽の関数に差し替える。
区間の中の待ちを測らず、全てのパターンを全てのタグへ当てる、照合の最も重い場合にする。
`--write-tag-index` を渡すと、タグのパターンを持つ測る用の索引を書き出して終わる。
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
# 偽の dev-docs が返すタグの既定の件数（実際の dev-docs が返した最大 1,081 件以上）
DEFAULT_TAG_COUNT = 2000
# 測る用の索引の既定のエントリ数（エントリごとにタグのパターンを 2 つ持つ）
DEFAULT_TAG_ENTRIES = 152
# 測る用の索引のエントリが当てるツール
TAG_ENTRY_TOOL = "mcp__*__search_docs"

# 1 回の呼び出しの中でファイルを辿った時間（秒）
_scan_seconds: list[float] = []
_original_scan = check_tools.scan_unmatched
# 偽の dev-docs が返すタグ
_fake_tags: tuple[str, ...] = ()


def _timed_scan(*args, **kwargs):
    """ファイルを辿る時間を測って `_scan_seconds` に残す。"""
    started = time.perf_counter()
    try:
        return _original_scan(*args, **kwargs)
    finally:
        _scan_seconds.append(time.perf_counter() - started)


async def _unmatched_tags(url: str, project_dir: str, *, timeout: float) -> UsedTags:  # noqa: ASYNC109 -- 差し替える関数と同じ引数で受ける
    """どのパターンにも当たらないタグをすぐ返す。"""
    return UsedTags(tags=_fake_tags, reason=None)


def _write_tag_index(path: Path, rules: list[str], entries: int) -> None:
    """ルールの場所を順に使い回し、エントリごとに glob と正規表現のタグのパターンを 1 つずつ持つ索引を書く。"""
    lines = ["rules:"]
    for number in range(entries):
        lines += [
            f"  - rule: {rules[number % len(rules)]}",
            "    tools:",
            f'      - "{TAG_ENTRY_TOOL}"',
            "    args:",
            "      filter[tags]:",
            f'        - "unused-{number}-*"',
            f'        - "re:^unused-{number}-x$"',
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _check(project_dir: str, validator, response_format: str):
    """サーバーと同じ引数で `check_indexes` を 1 回呼ぶ。"""
    return await check_tools.check_indexes(
        project_dir=project_dir,
        format=response_format,
        env=os.environ,
        validator=validator,
        scan_time_limit=app.UNMATCHED_SCAN_TIME_LIMIT,
        dev_docs_timeout=app.DEV_DOCS_TIMEOUT,
    )


async def _call_once(project_dir: str, validator) -> dict:
    """既定の応答の形式で 1 回呼び、全体・辿る・残りの時間を返す。"""
    _scan_seconds.clear()
    started = time.perf_counter()
    result = await _check(project_dir, validator, "markdown")
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
    global _fake_tags
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", help="check_indexes の project_dir")
    parser.add_argument("--out", type=Path, help="結果の JSON Lines")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--tag-count", type=int, default=DEFAULT_TAG_COUNT)
    parser.add_argument("--write-tag-index", type=Path, help="測る用の索引の書き出し先")
    parser.add_argument("--rules", nargs="*", default=[], help="測る用の索引が指すルールの場所")
    parser.add_argument("--tag-entries", type=int, default=DEFAULT_TAG_ENTRIES)
    args = parser.parse_args()

    # 測る用の索引を書き出すだけのとき
    if args.write_tag_index is not None:
        _write_tag_index(args.write_tag_index, args.rules, args.tag_entries)
        return
    _fake_tags = tuple(f"measure-tag-{number:04d}" for number in range(args.tag_count))
    check_tools.scan_unmatched = _timed_scan
    check_tools.fetch_used_tags = _unmatched_tags
    # サーバーと同じく、検証器は起動時に 1 回だけ作る
    validator = load_validator()
    # 測る前に、タグの照合が走り、全てのパターンが使われていないと返ることを確かめて出す
    body = json.loads((await _check(args.project_dir, validator, "json")).content[0].text)
    unused = sum(len(index["unused_tag_patterns"]) for index in body["indexes"])
    print(
        f"tag_check={body['tag_check']['state']} unused_tag_patterns={unused} tags={len(_fake_tags)}"
    )
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
