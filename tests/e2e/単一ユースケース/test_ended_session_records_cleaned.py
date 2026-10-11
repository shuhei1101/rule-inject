"""単一ユースケース「終わったセッションの既読の記録が掃除される」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

GUIDED_SUFFIX = ".guided.txt"


def test_normal(
    make_index: Callable[..., Path],
    configure_index: Callable[..., None],
    write_aged_record: Callable[..., Path],
    run_claude: Callable[..., Any],
) -> None:
    """セッションの開始で、保持期間を過ぎた既読の記録ファイルと案内済みの記録ファイルだけが消える（正常シナリオ）。"""
    # 準備
    configure_index(make_index())
    expired = write_aged_record("expired-session", 31)
    within = write_aged_record("within-session", 29)
    expired_guided = write_aged_record("expired-session", 31, suffix=GUIDED_SUFFIX)
    within_guided = write_aged_record("within-session", 29, suffix=GUIDED_SUFFIX)
    prompt = "ツールは呼ばずに、「了解」とだけ答えてください。"
    # 実行
    run_claude(prompt, max_turns=1)
    # 検証
    assert not expired.exists()
    assert within.exists()
    assert not expired_guided.exists()
    assert within_guided.exists()
