"""単一ユースケース「rule-injectを更新する」の E2E テスト。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

# テストの commit の作者（利用者の git の設定を読まない）
GIT_IDENTITY = ["-c", "user.name=test", "-c", "user.email=test@example.com"]

# 上流へ積む、どの設定にも当たる移し替えの手順
MIGRATION_MODULE = '''"""E2E テストの移し替えの手順。"""

DESCRIPTION = "E2E テストの移し替え"


def applies(data: object) -> bool:
    """どの設定にも当たる。"""
    return True


def apply(data: object) -> dict[str, str]:
    """何も変えない。"""
    return {}
'''
SERVICE_PATH = "src/rule_inject/features/migrate/service.py"


def _git(cwd: Path, *args: str) -> None:
    """cwd で git を実行する。"""
    subprocess.run(["git", *GIT_IDENTITY, *args], cwd=cwd, capture_output=True, check=True)


def _push_migration(clone_repos: Any) -> str:
    """移し替えの手順を 1 つ足して `MIGRATIONS` に並べた commit を、上流へ push して返す。"""
    pusher = clone_repos.pusher
    (pusher / "src/rule_inject/features/migrate/migrations/v9_9_9.py").write_text(
        MIGRATION_MODULE, encoding="utf-8"
    )
    service = pusher / SERVICE_PATH
    text = service.read_text(encoding="utf-8")
    service.write_text(
        text.replace(
            "from rule_inject.features.migrate.migrations import v0_2_3\n",
            "from rule_inject.features.migrate.migrations import v0_2_3, v9_9_9\n",
        ).replace("MIGRATIONS = (v0_2_3,)", "MIGRATIONS = (v0_2_3, v9_9_9)"),
        encoding="utf-8",
    )
    return clone_repos.push("migration.txt")


def test_normal(
    clone_repos: Any,
    serve_from_clone: Callable[[], Any],
    wait_restarted: Callable[..., dict[str, Any]],
) -> None:
    """上流の commit を取り込み、依存を入れ直して起動し直す（正常シナリオ）。"""
    # 準備
    server = serve_from_clone()
    before = server.call("get_server_status").structured_content
    upstream = clone_repos.push("added.txt")
    # 実行
    result = server.call("update_server")
    after = wait_restarted(server, before["started_at"])
    # 検証
    content = result.structured_content
    assert content["state"] == "restarting"
    assert content["before"] == before["commit"]
    assert content["after"] == upstream
    assert clone_repos.head() == upstream
    assert after["commit"] == upstream
    assert after["started_at"] > before["started_at"]


def test_normal_when_up_to_date(clone_repos: Any, serve_from_clone: Callable[[], Any]) -> None:
    """新しい commit が無ければ、何も変えずに最新である旨を受け取る（正常シナリオ）。"""
    # 準備
    server = serve_from_clone()
    before = server.call("get_server_status").structured_content
    # 実行
    result = server.call("update_server")
    status = server.call("get_server_status").structured_content
    # 検証
    assert result.structured_content["state"] == "up_to_date"
    assert status["started_at"] == before["started_at"]


def test_normal_when_migration_required(
    clone_repos: Any, serve_from_clone: Callable[[], Any], server_config_path: Path
) -> None:
    """設定の移し替えが要るときは起動し直さず、手順と global-setup の案内を受け取る（正常シナリオ）。"""
    # 準備
    server = serve_from_clone()
    before = server.call("get_server_status").structured_content
    config_before = server_config_path.read_text(encoding="utf-8")
    _push_migration(clone_repos)
    # 実行
    result = server.call("update_server")
    status = server.call("get_server_status").structured_content
    # 検証
    content = result.structured_content
    assert content["state"] == "migration_required"
    assert content["steps"] == ["E2E テストの移し替え"]
    assert "global-setup" in content["output"]
    assert status["started_at"] == before["started_at"]
    assert server_config_path.read_text(encoding="utf-8") == config_before


def test_error_when_not_fast_forward(
    clone_repos: Any,
    serve_from_clone: Callable[[], Any],
    tool_text: Callable[[Any], str],
) -> None:
    """クローンと上流が分かれていれば、クローンに触らずにエラーを受け取る（異常シナリオ）。"""
    # 準備
    server = serve_from_clone()
    before = server.call("get_server_status").structured_content
    clone_repos.push("upstream.txt")
    (clone_repos.clone / "local.txt").write_text("local\n", encoding="utf-8")
    _git(clone_repos.clone, "add", "local.txt")
    _git(clone_repos.clone, "commit", "-m", "local")
    local = clone_repos.head()
    # 実行
    result = server.call("update_server")
    status = server.call("get_server_status").structured_content
    # 検証
    assert result.is_error is True
    assert "fast-forward" in tool_text(result)
    assert clone_repos.head() == local
    assert status["started_at"] == before["started_at"]


def test_error_when_uncommitted_changes(
    clone_repos: Any,
    serve_from_clone: Callable[[], Any],
    tool_text: Callable[[Any], str],
) -> None:
    """commit していない変更があれば、クローンに触らずにエラーを受け取る（異常シナリオ）。"""
    # 準備
    server = serve_from_clone()
    before = server.call("get_server_status").structured_content
    head = clone_repos.head()
    clone_repos.push("upstream.txt")
    (clone_repos.clone / "README.md").write_text("changed\n", encoding="utf-8")
    # 実行
    result = server.call("update_server")
    status = server.call("get_server_status").structured_content
    # 検証
    assert result.is_error is True
    assert "commit していない変更" in tool_text(result)
    assert clone_repos.head() == head
    assert (clone_repos.clone / "README.md").read_text(encoding="utf-8") == "changed\n"
    assert status["started_at"] == before["started_at"]
