"""単一ユースケース「リポジトリの索引を登録する」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

SKILL = "/rule-inject:setup"
EMPTY_SETTINGS = "global:\n  log_retention_days: 3\n"


def _place(path: Path, text: str) -> None:
    """ファイルを配置する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_normal(
    setup_env: Any,
    e2e_project: Path,
    resident_for_setup: Callable[[], Any],
    run_skill_with_mcp: Callable[[str, Any], Any],
) -> None:
    """直下の `rules.yaml` は既定で読まれるため端末の設定を変えず、チェックの結果を示す（正常シナリオ）。"""
    # 準備
    _place(setup_env.config_file, EMPTY_SETTINGS)
    _place(e2e_project / "rules.yaml", "rules: []\n")
    server = resident_for_setup()
    # 実行
    run = run_skill_with_mcp(SKILL, server)
    # 検証
    assert setup_env.config_file.read_text(encoding="utf-8") == EMPTY_SETTINGS
    assert "rules.yaml" in run.answer


def test_normal_when_custom_index(
    setup_env: Any,
    e2e_project: Path,
    resident_for_setup: Callable[[], Any],
    run_skill_with_mcp: Callable[[str, Any], Any],
) -> None:
    """別の場所の索引を端末の設定の `projects` に記載する（正常シナリオ）。"""
    # 準備
    _place(setup_env.config_file, EMPTY_SETTINGS)
    _place(e2e_project / "rules" / "project.yaml", "rules: []\n")
    server = resident_for_setup()
    # 実行
    run = run_skill_with_mcp(f"{SKILL} rules/project.yaml", server)
    # 検証
    written = setup_env.config_file.read_text(encoding="utf-8")
    assert str(e2e_project) in written
    assert "rules/project.yaml" in written
    assert "rules/project.yaml" in run.answer


def test_error_when_settings_missing(
    setup_env: Any,
    run_skill: Callable[[str], Any],
) -> None:
    """端末の設定が無ければ `global-setup` を案内して止まる（異常シナリオ）。"""
    # 実行
    run = run_skill(SKILL)
    # 検証
    assert not setup_env.config_file.exists()
    assert "global-setup" in run.answer


def test_error_when_index_missing(
    setup_env: Any,
    run_skill: Callable[[str], Any],
) -> None:
    """索引が無ければ端末の設定を変えずに止まる（異常シナリオ）。"""
    # 準備
    _place(setup_env.config_file, EMPTY_SETTINGS)
    # 実行
    run = run_skill(SKILL)
    # 検証
    assert setup_env.config_file.read_text(encoding="utf-8") == EMPTY_SETTINGS
    assert "索引" in run.answer


def test_error_when_server_unreachable(
    setup_env: Any,
    e2e_project: Path,
    run_skill: Callable[[str], Any],
) -> None:
    """サーバーへ接続できなければ端末の設定を変えずに起動を案内する（異常シナリオ）。"""
    # 準備
    _place(setup_env.config_file, EMPTY_SETTINGS)
    _place(e2e_project / "rules.yaml", "rules: []\n")
    # 実行
    run = run_skill(SKILL)
    # 検証
    assert setup_env.config_file.read_text(encoding="utf-8") == EMPTY_SETTINGS
    assert "global-setup" in run.answer
