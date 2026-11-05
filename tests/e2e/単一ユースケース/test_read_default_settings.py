"""単一ユースケース「既定の場所の設定を読む」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

WRITE_PROMPT = "Write で {target} に「hello」と書いてください。他のことはしないでください。"


def _write_default_settings(tmp_path: Path, text: str) -> Path:
    """既定の場所（`XDG_CONFIG_HOME` の下）に設定ファイルを配置する。"""
    config = tmp_path / "config" / "rule-inject" / "settings.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(text, encoding="utf-8")
    return config


def test_normal(
    tmp_path: Path,
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_env: Callable[..., None],
    run_claude: Callable[..., Any],
) -> None:
    """`RULE_INJECT_CONFIG` が無くても既定の場所の設定の索引で案内される（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    index = make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]})
    _write_default_settings(tmp_path, f'global:\n  indexes:\n    - "{index}"\n')
    configure_env()
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write"])
    # 検証
    assert "Write" in run.denied_tools
    assert str(rule) in run.denial_reasons[0]


def test_normal_when_file_missing(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    configure_env: Callable[..., None],
    run_claude: Callable[..., Any],
) -> None:
    """既定の場所にファイルが無ければ設定なしで動き、プロジェクトの索引で案内される（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    (e2e_project / "rules.yaml").write_text(
        f'rules:\n  - rule: {rule}\n    paths:\n      - "**/*.txt"\n    on: [write]\n',
        encoding="utf-8",
    )
    configure_env()
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write"])
    # 検証
    assert "Write" in run.denied_tools
    assert str(rule) in run.denial_reasons[0]
    assert "settings.yaml" not in run.denial_reasons[0]


def test_error_when_unreadable(
    tmp_path: Path,
    e2e_project: Path,
    configure_env: Callable[..., None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """既定の場所のファイルが読めないとき、場所と理由が案内に載り、ログに残る（異常シナリオ）。"""
    # 準備
    config = _write_default_settings(tmp_path, "global:\n  foo: 1\n")
    configure_env()
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write"])
    # 検証
    text = transcript_text(run.session_id)
    logs = tmp_path / "xdg_state" / "rule-inject" / "logs"
    assert str(config) in text
    assert "foo" in text
    assert "read_settings" in "".join(path.read_text(encoding="utf-8") for path in logs.iterdir())
