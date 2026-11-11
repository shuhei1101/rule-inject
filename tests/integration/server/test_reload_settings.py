"""インターフェース定義『設定の再読込』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def test_normal(shared_server: Any, tmp_path: Path) -> None:
    """設定ファイルを再読込、読んだ値を返却する（正常系）。"""
    # 準備
    index = tmp_path / "added.yaml"
    shared_server.config_path.write_text(
        f"global:\n  indexes:\n    - {index}\n  log_retention_days: 7\n", encoding="utf-8"
    )
    # 実行
    result = shared_server.call("reload_settings")
    # 検証
    content = result.structured_content
    assert result.is_error is False
    assert content["config_path"] == str(shared_server.config_path)
    assert content["indexes"] == [str(index)]
    assert content["log_retention_days"] == 7
    assert shared_server.config_path.read_text(encoding="utf-8") == (
        f"global:\n  indexes:\n    - {index}\n  log_retention_days: 7\n"
    )


def test_normal_when_project_given(
    running_server: Callable[..., Any], project_dir: Path, tmp_path: Path
) -> None:
    """`project_dir` を受けると、そのプロジェクトで読む索引を返却する（正常系）。"""
    # 準備
    global_index = tmp_path / "global.yaml"
    project_index = tmp_path / "project.yaml"
    server = running_server(project_index, global_indexes=[global_index])
    # 実行
    result = server.call("reload_settings", project_dir=str(project_dir))
    # 検証
    assert result.structured_content["indexes"] == [str(global_index), str(project_index)]


def test_error_when_settings_unreadable(
    shared_server: Any,
    invalid_config: Callable[[], str],
    text_of: Callable[[Any], str],
) -> None:
    """読めない設定ファイルは場所と理由をエラーで返却し、待ち受けは続ける（異常系）。"""
    # 準備
    config = invalid_config()
    # 実行
    result = shared_server.call("reload_settings")
    status = shared_server.call("get_server_status")
    # 検証
    assert result.is_error is True
    assert config in text_of(result)
    assert "foo" in text_of(result)
    assert status.is_error is False
