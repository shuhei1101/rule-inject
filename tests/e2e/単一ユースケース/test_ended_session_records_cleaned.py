"""単一ユースケース「終わったセッションの既読の記録が掃除される」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def test_normal(
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    write_aged_record: Callable[[str, int], Path],
    run_claude: Callable[..., Any],
) -> None:
    """セッションの開始で、保持期間を過ぎた記録ファイルだけが消える（正常シナリオ）。"""
    # 準備
    configure_index(make_index())
    expired = write_aged_record("expired-session", 31)
    within = write_aged_record("within-session", 29)
    prompt = "ツールは呼ばずに、「了解」とだけ答えてください。"
    # 実行
    run_claude(prompt, max_turns=1)
    # 検証
    assert not expired.exists()
    assert within.exists()
