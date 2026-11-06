"""server/admin_tools.py の単体テスト。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

PORT = 8783
COMMIT_BEFORE = "a" * 40
COMMIT_AFTER = "b" * 40


def _commit_run(commit: str) -> Callable[..., Any]:
    """`git rev-parse HEAD` に commit を返す `RunCommand`。"""
    from rule_inject.server.clone import CommandResult

    def _run(
        args: Sequence[str],
        *,
        cwd: Path,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        """commit を標準出力に返す。"""
        return CommandResult(returncode=0, stdout=f"{commit}\n", stderr="")

    return _run


@pytest.fixture
def clone_dir(tmp_path: Path) -> Path:
    """`version.ini` を置いたクローンの代わりのフォルダ。"""
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / "version.ini").write_text("v0.2.4\n", encoding="utf-8")
    return clone


@pytest.fixture
def control() -> Any:
    """`should_exit` だけを持つ代わりのサーバーを受け取った `ServerControl`。"""
    from rule_inject.server.control import ServerControl

    server_control = ServerControl(port=PORT)
    server_control.attach(SimpleNamespace(should_exit=False))
    return server_control


@pytest.fixture
def stub_update(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """`pull`・`sync_dependencies`・`plan_migrations` を差し替え、呼ばれた順を返す factory。"""
    from rule_inject.server import admin_tools
    from rule_inject.server.clone import PullOutcome, UpdateFailedError

    def _stub(
        *, pulled: bool, migrations: list[str] | None = None, sync_fails: bool = False
    ) -> list[str]:
        """差し替える関数の結果を決める。"""
        calls: list[str] = []

        def _pull(clone: Path, *, run: Any) -> PullOutcome:
            calls.append("pull")
            after = COMMIT_AFTER if pulled else COMMIT_BEFORE
            return PullOutcome(before=COMMIT_BEFORE, after=after, pulled=pulled)

        def _sync(clone: Path, env: Mapping[str, str], *, run: Any) -> None:
            calls.append("sync")
            if sync_fails:
                raise UpdateFailedError("uv sync --extra server が終了コード 1 で終わった")

        def _plan(clone: Path, env: Mapping[str, str], *, run: Any) -> list[str]:
            calls.append("plan")
            return list(migrations or [])

        monkeypatch.setattr(admin_tools, "pull", _pull)
        monkeypatch.setattr(admin_tools, "sync_dependencies", _sync)
        monkeypatch.setattr(admin_tools, "plan_migrations", _plan)
        return calls

    return _stub


def test_get_server_status(
    server_env: Callable[..., dict[str, str]], clone_dir: Path, control: Any
) -> None:
    """稼働の状態とクローンを返す（正常系）。"""
    from rule_inject.server.admin_tools import get_server_status

    # 準備
    env = server_env("global:\n  indexes: []\n")
    # 実行
    result = get_server_status(env=env, control=control, clone=clone_dir, run=_commit_run(COMMIT_BEFORE))
    # 検証
    content = result.structured_content
    assert result.is_error is False
    assert content["version"] == "v0.2.4"
    assert content["commit"] == COMMIT_BEFORE
    assert content["port"] == PORT
    assert content["pid"] == control.pid
    assert content["config"]["readable"] is True
    assert content["config"]["path"] == env["RULE_INJECT_CONFIG"]
    assert content["restarting"] is False


def test_get_server_status_when_settings_unreadable(
    server_env: Callable[..., dict[str, str]], clone_dir: Path, control: Any
) -> None:
    """設定ファイルが読めなくてもエラーにしない（正常系）。"""
    from rule_inject.server.admin_tools import get_server_status

    # 準備
    env = server_env("global:\n  unknown_key: 1\n")
    # 実行
    result = get_server_status(env=env, control=control, clone=clone_dir, run=_commit_run(COMMIT_BEFORE))
    # 検証
    content = result.structured_content
    assert result.is_error is False
    assert content["config"]["readable"] is False
    assert content["config"]["path"] == env["RULE_INJECT_CONFIG"]
    assert env["RULE_INJECT_CONFIG"] in content["config"]["error"]
    assert "unknown_key" in content["config"]["error"]


def test_reload_settings(server_env: Callable[..., dict[str, str]], tmp_path: Path) -> None:
    """読んだ値を返す（正常系）。"""
    from rule_inject.server.admin_tools import reload_settings

    # 準備
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    env = server_env(
        f"global:\n  indexes:\n    - {first}\n    - {second}\n  log_retention_days: 7\n"
    )
    # 実行
    result = reload_settings(env=env)
    # 検証
    content = result.structured_content
    assert content["indexes"] == [str(first), str(second)]
    assert content["log_retention_days"] == 7
    assert content["config_path"] == env["RULE_INJECT_CONFIG"]


def test_reload_settings_when_unreadable(server_env: Callable[..., dict[str, str]]) -> None:
    """読めない設定ファイル（異常系）。"""
    from rule_inject.server.admin_tools import reload_settings

    # 準備
    env = server_env("global:\n  unknown_key: 1\n")
    # 実行・検証
    with pytest.raises(ToolError, match="settings.yaml"):
        reload_settings(env=env)


def test_restart_server(control: Any) -> None:
    """再起動を始める（正常系）。"""
    from rule_inject.server.admin_tools import restart_server

    # 実行
    result = asyncio.run(restart_server(control=control))
    # 検証
    assert result.structured_content["restarting"] is True
    assert result.structured_content["pid"] == control.pid
    assert control.restarting is True


def test_update_server(
    control: Any, clone_dir: Path, stub_update: Callable[..., list[str]]
) -> None:
    """取り込んで再起動を始める（正常系）。"""
    from rule_inject.server.admin_tools import update_server

    # 準備
    calls = stub_update(pulled=True, migrations=[])
    # 実行
    result = asyncio.run(
        update_server(env={}, control=control, clone=clone_dir, run=_commit_run(COMMIT_AFTER))
    )
    # 検証
    content = result.structured_content
    assert content["state"] == "restarting"
    assert content["before"] == COMMIT_BEFORE
    assert content["after"] == COMMIT_AFTER
    assert calls == ["pull", "sync", "plan"]
    assert control.restarting is True


def test_update_server_when_up_to_date(
    control: Any, clone_dir: Path, stub_update: Callable[..., list[str]]
) -> None:
    """新しい commit が無ければ何もしない（正常系）。"""
    from rule_inject.server.admin_tools import update_server

    # 準備
    calls = stub_update(pulled=False)
    # 実行
    result = asyncio.run(
        update_server(env={}, control=control, clone=clone_dir, run=_commit_run(COMMIT_BEFORE))
    )
    # 検証
    assert result.structured_content["state"] == "up_to_date"
    assert calls == ["pull"]
    assert control.restarting is False


def test_update_server_when_migration_required(
    control: Any, clone_dir: Path, stub_update: Callable[..., list[str]]
) -> None:
    """移し替えが要れば再起動しない（正常系）。"""
    from rule_inject.server.admin_tools import update_server

    # 準備
    stub_update(pulled=True, migrations=["global.server_port を削除し、env の RULE_INJECT_PORT へ移す"])
    # 実行
    result = asyncio.run(
        update_server(env={}, control=control, clone=clone_dir, run=_commit_run(COMMIT_AFTER))
    )
    # 検証
    content = result.structured_content
    assert content["state"] == "migration_required"
    assert content["steps"] == ["global.server_port を削除し、env の RULE_INJECT_PORT へ移す"]
    assert "global-setup" in content["output"]
    assert control.restarting is False


def test_update_server_when_failed(
    control: Any, clone_dir: Path, stub_update: Callable[..., list[str]]
) -> None:
    """失敗したら更新の印を下ろす（異常系）。"""
    from rule_inject.server.admin_tools import update_server
    from rule_inject.server.clone import UpdateFailedError

    # 準備
    stub_update(pulled=True, sync_fails=True)
    # 実行・検証
    with pytest.raises(UpdateFailedError, match="uv sync"):
        asyncio.run(
            update_server(env={}, control=control, clone=clone_dir, run=_commit_run(COMMIT_AFTER))
        )
    control.begin_update()
    assert control.restarting is False
