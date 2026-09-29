"""単一ユースケース「セッションの開始時に作業の決まりを受け取る」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

WORK_RULES_SNIPPET = "空の内容で作り"


def test_normal(
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """セッションの開始時に、空で作ってから書く決まりが記録に載る（正常シナリオ）。"""
    # 準備
    configure_index(make_index())
    prompt = "新しいファイルを作るときの手順を、設定から読み取ったとおりに答えてください。"
    # 実行
    run = run_claude(prompt, max_turns=1)
    # 検証
    assert WORK_RULES_SNIPPET in transcript_text(run.session_id)
