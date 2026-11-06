"""インターフェース定義『サーバーの再起動』の結合テスト。"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# 偽の dev-docs が応答を返すまでの秒数（check_indexes を処理中のままにする時間）
SLOW_DEV_DOCS_SEC = 4
# 処理中の呼び出しを始めてから、再起動を呼ぶまでの秒数
CALL_START_SEC = 1


def _slow_server(
    start_server: Callable[..., Any],
    start_fake_dev_docs: Callable[..., Any],
    make_index: Callable[..., Path],
    config_text: Callable[..., str],
    project_dir: Path,
) -> Any:
    """タグのパターンを持つ索引と、応答の遅い偽の dev-docs を指した設定ファイルで、サーバーを起動する。"""
    fake = start_fake_dev_docs(
        {"total_count": 1, "groups": [{"value": "python", "count": 1}]}, delay=SLOW_DEV_DOCS_SEC
    )
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(
        f'rules:\n  - rule: {rule}\n    args:\n      filter[tags]: ["python"]\n', "slow.yaml"
    )
    return start_server(
        lambda: config_text(match=project_dir, project_indexes=[index], dev_docs_url=fake.url)
    )


def _call_in_background(
    server: Any, name: str, **arguments: Any
) -> tuple[threading.Thread, list[Any]]:
    """別の接続でツールを呼ぶスレッドを始め、スレッドと結果を入れるリストを返す。"""
    results: list[Any] = []
    thread = threading.Thread(target=lambda: results.append(server.call(name, **arguments)))
    thread.start()
    return thread, results


def test_normal(
    start_server: Callable[..., Any],
    config_text: Callable[..., str],
    wait_restarted: Callable[..., dict[str, Any]],
) -> None:
    """応答を返し、処理中の呼び出しの終わりを待ってから待ち受けを閉じ、同じプロセスで起動し直す（正常系）。"""
    # 準備
    server = start_server(config_text)
    before = server.call("get_server_status").structured_content
    # 実行
    result = server.call("restart_server")
    after = wait_restarted(server, before["started_at"])
    # 検証
    assert result.structured_content["restarting"] is True
    assert result.structured_content["pid"] == before["pid"]
    assert after["pid"] == before["pid"]
    assert after["port"] == before["port"]
    assert after["started_at"] > before["started_at"]
    assert server.process.poll() is None


def test_normal_when_call_in_flight(
    start_server: Callable[..., Any],
    start_fake_dev_docs: Callable[..., Any],
    make_index: Callable[..., Path],
    config_text: Callable[..., str],
    project_dir: Path,
    wait_restarted: Callable[..., dict[str, Any]],
) -> None:
    """処理中の呼び出しの応答を返し終えてから待ち受けを閉じる（正常系）。"""
    # 準備
    server = _slow_server(start_server, start_fake_dev_docs, make_index, config_text, project_dir)
    before = server.call("get_server_status").structured_content
    thread, results = _call_in_background(
        server, "check_indexes", project_dir=str(project_dir), format="json"
    )
    time.sleep(CALL_START_SEC)
    # 実行
    restarted = server.call("restart_server")
    thread.join()
    after = wait_restarted(server, before["started_at"])
    # 検証
    assert restarted.structured_content["restarting"] is True
    assert results[0].is_error is False
    assert results[0].structured_content["tag_check"]["state"] == "checked"
    assert after["started_at"] > before["started_at"]


def test_error_when_restart_in_progress(
    start_server: Callable[..., Any],
    start_fake_dev_docs: Callable[..., Any],
    make_index: Callable[..., Path],
    config_text: Callable[..., str],
    project_dir: Path,
    wait_restarted: Callable[..., dict[str, Any]],
    text_of: Callable[[Any], str],
) -> None:
    """処理中の呼び出しを待つ間の 2 回目の再起動を断る（異常系）。"""
    # 準備
    server = _slow_server(start_server, start_fake_dev_docs, make_index, config_text, project_dir)
    before = server.call("get_server_status").structured_content
    thread, _ = _call_in_background(
        server, "check_indexes", project_dir=str(project_dir), format="json"
    )
    time.sleep(CALL_START_SEC)
    server.call("restart_server")
    # 実行
    second = server.call("restart_server")
    listed = server.call("list_rules", project_dir=str(project_dir))
    status = server.call("get_server_status")
    thread.join()
    after = wait_restarted(server, before["started_at"])
    # 検証
    assert second.is_error is True
    assert "再起動の途中" in text_of(second)
    assert listed.is_error is True
    assert "再起動の途中" in text_of(listed)
    assert status.structured_content["restarting"] is True
    assert server.stderr_text().count("Uvicorn running on") == 2
    assert after["started_at"] > before["started_at"]
