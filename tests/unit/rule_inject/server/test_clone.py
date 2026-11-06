"""server/clone.py の単体テスト。"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

# テストの commit の作者（利用者の git の設定を読まない）
GIT_IDENTITY = ["-c", "user.name=test", "-c", "user.email=test@example.com"]


def _git(cwd: Path, *args: str) -> str:
    """cwd で git を実行し、標準出力を返す。"""
    completed = subprocess.run(
        ["git", *GIT_IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


@dataclass(frozen=True)
class Repos:
    """上流の bare リポジトリと、そこから取ったクローンと、上流へ commit を積む作業用のクローン。"""

    upstream: Path
    clone: Path
    pusher: Path


@pytest.fixture
def repos(tmp_path: Path) -> Repos:
    """1 つの commit を持つ上流と、そこから取ったクローンを作る。"""
    upstream = tmp_path / "upstream.git"
    pusher = tmp_path / "pusher"
    clone = tmp_path / "clone"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(upstream)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(upstream), str(pusher)], check=True, capture_output=True)
    (pusher / "version.ini").write_text("v0.2.4\n", encoding="utf-8")
    _git(pusher, "add", "version.ini")
    _git(pusher, "commit", "-m", "first")
    _git(pusher, "push", "origin", "main")
    subprocess.run(["git", "clone", str(upstream), str(clone)], check=True, capture_output=True)
    return Repos(upstream=upstream, clone=clone, pusher=pusher)


@pytest.fixture
def push_commit() -> Callable[[Path, str], str]:
    """repo にファイルを 1 つ足して commit し、上流があれば push して、commit を返す factory。"""

    def _push(repo: Path, name: str, *, push: bool = True) -> str:
        """repo に name のファイルを足して commit する。"""
        (repo / name).write_text(name, encoding="utf-8")
        _git(repo, "add", name)
        _git(repo, "commit", "-m", name)
        if push:
            _git(repo, "push", "origin", "main")
        return _git(repo, "rev-parse", "HEAD")

    return _push


@pytest.fixture
def recording_run() -> tuple[Callable[..., object], list[list[str]]]:
    """`run_command` を呼びつつ、呼ばれたコマンドを記録する `RunCommand`。"""
    from rule_inject.server.clone import CommandResult, run_command

    calls: list[list[str]] = []

    def _run(
        args: Sequence[str],
        *,
        cwd: Path,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        """コマンドを記録してから実行する。"""
        calls.append(list(args))
        return run_command(args, cwd=cwd, timeout=timeout, env=env)

    return _run, calls


def _stub_run(returncode: int, stdout: str = "", stderr: str = "") -> Callable[..., object]:
    """常に同じ結果を返す `RunCommand`。"""
    from rule_inject.server.clone import CommandResult

    def _run(
        args: Sequence[str],
        *,
        cwd: Path,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        """決めた結果を返す。"""
        return CommandResult(returncode=returncode, stdout=stdout, stderr=stderr)

    return _run


def test_find_clone(tmp_path: Path) -> None:
    """version.ini を持つフォルダを返す（正常系）。"""
    from rule_inject.server.clone import find_clone

    # 準備
    (tmp_path / "version.ini").write_text("v0.2.4\n", encoding="utf-8")
    start = tmp_path / "src" / "rule_inject" / "server"
    start.mkdir(parents=True)
    # 実行
    found = find_clone(start)
    # 検証
    assert found == tmp_path


def test_read_version_when_missing(tmp_path: Path) -> None:
    """ファイルが無ければ None（正常系）。"""
    from rule_inject.server.clone import read_version

    # 実行
    version = read_version(tmp_path)
    # 検証
    assert version is None


def test_head_commit_when_not_git(tmp_path: Path) -> None:
    """git のリポジトリでなければ None（正常系）。"""
    from rule_inject.server.clone import head_commit

    # 実行
    commit = head_commit(tmp_path, run=_stub_run(128, stderr="fatal: not a git repository"))
    # 検証
    assert commit is None


def test_run_command_when_timeout(tmp_path: Path) -> None:
    """上限を超えたら打ち切る（異常系）。"""
    from rule_inject.server.clone import UpdateFailedError, run_command

    # 準備
    args = [sys.executable, "-c", "import time; time.sleep(5)"]
    # 実行・検証
    with pytest.raises(UpdateFailedError, match="0.2"):
        run_command(args, cwd=tmp_path, timeout=0.2)


def test_pull(repos: Repos, push_commit: Callable[..., str]) -> None:
    """上流の commit を取り込む（正常系）。"""
    from rule_inject.server.clone import pull, run_command

    # 準備
    upstream_commit = push_commit(repos.pusher, "second.txt")
    # 実行
    outcome = pull(repos.clone, run=run_command)
    # 検証
    assert outcome.pulled is True
    assert outcome.after == upstream_commit
    assert _git(repos.clone, "rev-parse", "HEAD") == upstream_commit


def test_pull_when_ahead(repos: Repos, push_commit: Callable[..., str]) -> None:
    """クローンが先に進んでいるだけなら取り込まない（正常系）。"""
    from rule_inject.server.clone import pull, run_command

    # 準備
    local_commit = push_commit(repos.clone, "local.txt", push=False)
    # 実行
    outcome = pull(repos.clone, run=run_command)
    # 検証
    assert outcome.pulled is False
    assert outcome.before == local_commit
    assert outcome.after == local_commit


def test_pull_when_diverged(repos: Repos, push_commit: Callable[..., str]) -> None:
    """分かれていれば断る（異常系）。"""
    from rule_inject.server.clone import UpdateFailedError, pull, run_command

    # 準備
    push_commit(repos.pusher, "upstream.txt")
    local_commit = push_commit(repos.clone, "local.txt", push=False)
    # 実行・検証
    with pytest.raises(UpdateFailedError, match="fast-forward"):
        pull(repos.clone, run=run_command)
    assert _git(repos.clone, "rev-parse", "HEAD") == local_commit


def test_pull_when_dirty(
    repos: Repos,
    push_commit: Callable[..., str],
    recording_run: tuple[Callable[..., object], list[list[str]]],
) -> None:
    """commit していない変更があれば取得もしない（異常系）。"""
    from rule_inject.server.clone import UpdateFailedError, pull

    # 準備
    push_commit(repos.pusher, "second.txt")
    (repos.clone / "version.ini").write_text("changed\n", encoding="utf-8")
    run, calls = recording_run
    # 実行・検証
    with pytest.raises(UpdateFailedError, match="version.ini"):
        pull(repos.clone, run=run)
    assert ["git", "fetch"] not in calls


def test_plan_migrations(tmp_path: Path) -> None:
    """migrations を返す（正常系）。"""
    from rule_inject.server.clone import plan_migrations

    # 準備
    stdout = '{"steps": ["version を 0.2.5 にする"], "migrations": []}'
    # 実行
    migrations = plan_migrations(tmp_path, {}, run=_stub_run(0, stdout=stdout))
    # 検証
    assert migrations == []


def test_plan_migrations_when_newer(tmp_path: Path) -> None:
    """設定がツールより新しい（異常系）。"""
    from rule_inject.server.clone import UpdateFailedError, plan_migrations

    # 準備
    run = _stub_run(6, stderr="設定のバージョン 9.0.0 はツールのバージョン 0.2.4 より新しい")
    # 実行・検証
    with pytest.raises(UpdateFailedError, match="6"):
        plan_migrations(tmp_path, {}, run=run)
