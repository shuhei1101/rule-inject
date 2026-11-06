"""単一ユースケース「MCPサーバーを再起動する」の E2E テスト。"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

# 偽の dev-docs が応答を返すまでの秒数（check_indexes を処理中のままにする時間）
SLOW_DEV_DOCS_SEC = 10
# 処理中の呼び出しを始めてから、再起動を呼ぶまでの秒数
CALL_START_SEC = 1


def test_normal(serve: Callable[..., Any], wait_restarted: Callable[..., dict[str, Any]]) -> None:
    """再起動を呼ぶと、接続し直した後の状態の確認で起動した時刻が新しくなる（正常シナリオ）。"""
    # 準備
    server = serve()
    before = server.call("get_server_status").structured_content
    # 実行
    result = server.call("restart_server")
    after = wait_restarted(server, before["started_at"])
    # 検証
    assert result.structured_content["restarting"] is True
    assert after["port"] == before["port"]
    assert after["started_at"] > before["started_at"]
    assert server.process.poll() is None


def test_error_when_restart_in_progress(
    serve: Callable[..., Any],
    start_dev_docs: Callable[..., str],
    make_rule: Callable[..., Path],
    tmp_path: Path,
    e2e_project: Path,
    wait_restarted: Callable[..., dict[str, Any]],
    tool_text: Callable[[Any], str],
) -> None:
    """再起動の途中の 2 回目を断り、起動し直すのは 1 回だけ（異常シナリオ）。"""
    # 準備
    url = start_dev_docs(
        {"total_count": 1, "groups": [{"value": "python", "count": 1}]}, delay=SLOW_DEV_DOCS_SEC
    )
    rule = make_rule("slow.md", "# slow\n")
    index = tmp_path / "slow.yaml"
    index.write_text(
        f'rules:\n  - rule: {rule}\n    args:\n      filter[tags]: ["python"]\n', encoding="utf-8"
    )
    server = serve(index, dev_docs_url=url)
    before = server.call("get_server_status").structured_content
    results: list[Any] = []
    thread = threading.Thread(
        target=lambda: results.append(
            server.call("check_indexes", project_dir=str(e2e_project), format="json")
        )
    )
    thread.start()
    time.sleep(CALL_START_SEC)
    server.call("restart_server")
    # 実行
    second = server.call("restart_server")
    thread.join()
    after = wait_restarted(server, before["started_at"])
    # 検証
    assert second.is_error is True
    assert "再起動の途中" in tool_text(second)
    assert results[0].is_error is False
    assert server.stderr_text().count("Uvicorn running on") == 2
    assert after["started_at"] > before["started_at"]
