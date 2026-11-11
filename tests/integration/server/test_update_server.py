"""インターフェース定義『サーバーの更新』の結合テスト。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

# テストの commit の作者（利用者の git の設定を読まない）
GIT_IDENTITY = ["-c", "user.name=test", "-c", "user.email=test@example.com"]
# 上流へ追加する、どの設定にも該当する移し替えの手順
MIGRATION_MODULE = '''"""結合テストの移し替えの手順。"""

DESCRIPTION = "結合テストの移し替え"


def applies(data: object) -> bool:
    """どの設定にも該当する。"""
    return True


def apply(data: object) -> dict[str, str]:
    """何も変えない。"""
    return {}
'''
SERVICE_PATH = "src/rule_inject/features/migrate/service.py"


def _git(cwd: Path, *args: str) -> str:
    """cwd で git を実行し、標準出力を返却する。"""
    completed = subprocess.run(
        ["git", *GIT_IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


def _push_migration(pusher: Path) -> str:
    """移し替えの手順を 1 つ追加して `MIGRATIONS` に並べた commit を、上流へ push して返却する。"""
    (pusher / "src/rule_inject/features/migrate/migrations/v9_9_9.py").write_text(
        MIGRATION_MODULE, encoding="utf-8"
    )
    service = pusher / SERVICE_PATH
    text = service.read_text(encoding="utf-8")
    text = text.replace(
        "from rule_inject.features.migrate.migrations import v0_2_3\n",
        "from rule_inject.features.migrate.migrations import v0_2_3, v9_9_9\n",
    ).replace("MIGRATIONS = (v0_2_3,)", "MIGRATIONS = (v0_2_3, v9_9_9)")
    service.write_text(text, encoding="utf-8")
    _git(pusher, "add", "-A")
    _git(pusher, "commit", "-m", "migration")
    _git(pusher, "push", "-q", "origin", "HEAD")
    return _git(pusher, "rev-parse", "HEAD")


def test_normal(
    clone_repos: Any,
    start_clone_server: Callable[..., Any],
    wait_restarted: Callable[..., dict[str, Any]],
) -> None:
    """上流の commit を fast-forward で取り込み、依存を再インストール、移し替えが要らなければ再起動する（正常系）。"""
    # 準備
    server = start_clone_server()
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


def test_normal_when_up_to_date(clone_repos: Any, start_clone_server: Callable[..., Any]) -> None:
    """上流に新しい commit が無いときは、クローンにも依存にも触らず再起動もしない（正常系）。"""
    # 準備
    server = start_clone_server()
    before = server.call("get_server_status").structured_content
    # 実行
    result = server.call("update_server")
    status = server.call("get_server_status").structured_content
    # 検証
    content = result.structured_content
    assert content["state"] == "up_to_date"
    assert content["before"] == content["after"]
    assert status["started_at"] == before["started_at"]
    assert not (clone_repos.clone / ".venv").exists()


def test_normal_when_migration_required(
    clone_repos: Any, start_clone_server: Callable[..., Any]
) -> None:
    """移し替えの手順があるときは再起動せず、手順と global-setup を返却する（正常系）。"""
    # 準備
    server = start_clone_server()
    before = server.call("get_server_status").structured_content
    config_before = server.config_path.read_text(encoding="utf-8")
    upstream = _push_migration(clone_repos.pusher)
    # 実行
    result = server.call("update_server")
    status = server.call("get_server_status").structured_content
    # 検証
    content = result.structured_content
    assert content["state"] == "migration_required"
    assert content["steps"] == ["結合テストの移し替え"]
    assert "global-setup" in content["output"]
    assert clone_repos.head() == upstream
    assert status["started_at"] == before["started_at"]
    assert server.config_path.read_text(encoding="utf-8") == config_before


def test_error_when_not_fast_forward(
    clone_repos: Any,
    start_clone_server: Callable[..., Any],
    text_of: Callable[[Any], str],
) -> None:
    """上流から分かれた commit があるときは、クローンに触らず再起動もしない（異常系）。"""
    # 準備
    server = start_clone_server()
    upstream = clone_repos.push("upstream.txt")
    (clone_repos.clone / "local.txt").write_text("local\n", encoding="utf-8")
    _git(clone_repos.clone, "add", "local.txt")
    _git(clone_repos.clone, "commit", "-m", "local")
    local = clone_repos.head()
    # 実行
    result = server.call("update_server")
    # 検証
    assert result.is_error is True
    assert "fast-forward" in text_of(result)
    assert local in text_of(result)
    assert upstream in text_of(result)
    assert clone_repos.head() == local


def test_error_when_uncommitted_changes(
    clone_repos: Any,
    start_clone_server: Callable[..., Any],
    text_of: Callable[[Any], str],
) -> None:
    """追跡しているファイルに commit していない変更があるときは、取得もせずに断る（異常系）。"""
    # 準備
    server = start_clone_server()
    head = clone_repos.head()
    clone_repos.push("upstream.txt")
    (clone_repos.clone / "README.md").write_text("changed\n", encoding="utf-8")
    # 実行
    result = server.call("update_server")
    # 検証
    assert result.is_error is True
    assert "commit していない変更" in text_of(result)
    assert "README.md" in text_of(result)
    assert clone_repos.head() == head
    assert (clone_repos.clone / "README.md").read_text(encoding="utf-8") == "changed\n"


def test_error_when_command_failed(
    clone_repos: Any,
    start_clone_server: Callable[..., Any],
    text_of: Callable[[Any], str],
) -> None:
    """`uv sync` が失敗したときは、取り込んだ commit を返却して再起動しない（異常系）。"""
    # 準備
    server = start_clone_server(fail_uv=True)
    before = server.call("get_server_status").structured_content
    upstream = clone_repos.push("added.txt")
    # 実行
    result = server.call("update_server")
    status = server.call("get_server_status").structured_content
    # 検証
    assert result.is_error is True
    assert "sync" in text_of(result)
    assert "終了コード 1" in text_of(result)
    assert "uv sync に失敗した" in text_of(result)
    assert upstream in text_of(result)
    assert status["started_at"] == before["started_at"]
