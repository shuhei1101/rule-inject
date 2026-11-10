"""確認: メインのクローンに rules.yaml があり、置いた後のログにこの場所の読み込みの失敗が無いかを確かめる（状態は変えない）。"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from _common import INDEX, LOG_DIR


def main() -> int:
    """結果の行を出し、failed があれば 1 を返す。"""
    if not INDEX.is_file():
        print(f"索引のファイル: failed（{INDEX} が無い）")
        return 1
    placed_at = datetime.fromtimestamp(INDEX.stat().st_mtime, tz=UTC)
    print(f"索引のファイル: ok（{placed_at.isoformat()}）")

    # 索引を置いた時刻より後の、この場所の FileNotFoundError の行を数える
    failures = 0
    for log in sorted(LOG_DIR.glob("*_rule-inject.log")):
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            # この索引の場所の、ファイルが無いことによる失敗の行だけを数える
            if record.get("path") != str(INDEX):
                continue
            if "FileNotFoundError" not in str(record.get("reason", "")):
                continue
            if datetime.fromisoformat(record["time"]) > placed_at:
                failures += 1
    if failures:
        print(f"索引の読み込みの失敗: failed（{failures} 行）")
        return 1
    print("索引の読み込みの失敗: ok（0 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
