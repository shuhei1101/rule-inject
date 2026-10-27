"""単一ユースケース「古いログが掃除される」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


def test_normal(
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    write_dated_log: Callable[[date], Path],
    run_claude: Callable[..., Any],
) -> None:
    """セッションの開始で、日付が保持日数以上前のログのファイルだけが削除される（正常シナリオ）。"""
    # 準備
    configure_index(make_index())
    today = datetime.now(UTC).date()
    expired = write_dated_log(today - timedelta(days=3))
    within = write_dated_log(today - timedelta(days=2))
    prompt = "ツールは呼ばずに、「了解」とだけ答えてください。"
    # 実行
    run_claude(prompt, max_turns=1)
    # 検証
    assert not expired.exists()
    assert within.exists()
