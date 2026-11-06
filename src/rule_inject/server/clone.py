"""サーバーが動いているクローンの操作（バージョン・commit・上流の取り込み・依存の入れ直し・移し替えの確かめ）。"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from mcp.server.mcpserver.exceptions import ToolError

# クローンの直下のバージョンのファイル
VERSION_FILE = "version.ini"
# git の各コマンドの打ち切りの上限（秒）
GIT_TIMEOUT = 49
# `uv sync` の打ち切りの上限（秒）
UV_SYNC_TIMEOUT = 864
# `migrate --plan` の打ち切りの上限（秒）
MIGRATE_PLAN_TIMEOUT = 57
# 失敗したコマンドの標準エラーから、誤りに載せる末尾の行数
STDERR_TAIL_LINES = 20
# `uv run` が子プロセスに置く、uv の実行ファイルの場所
UV_ENV = "UV"


class UpdateFailedError(ToolError):
    """更新の失敗（commit していない変更・上流が無い・fast-forward できない・コマンドの失敗）。"""


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandResult:
    """コマンドの終了コードと出力。"""

    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PullOutcome:
    """取り込みの前後の commit と、取り込んだか。"""

    before: str
    # 取り込まなかったときは before と同じ
    after: str
    # 偽なら up_to_date
    pulled: bool


class RunCommand(Protocol):
    """コマンドを上限つきで実行し、終了コードと出力を返す。"""

    def __call__(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        """args を cwd で実行する。"""
        ...


def find_clone(start: Path) -> Path:
    """start とその親を順に見て、`VERSION_FILE` を持つ最初のフォルダを返す。"""
    for folder in (start, *start.parents):
        if (folder / VERSION_FILE).is_file():
            return folder
    raise FileNotFoundError(f"{VERSION_FILE} を持つフォルダが {start} の上にありません")


def read_version(clone: Path) -> str | None:
    """クローンの `VERSION_FILE` の 1 行目を返す。ファイルが無いときは None。"""
    path = clone / VERSION_FILE
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[0].strip() if lines else None


def head_commit(clone: Path, *, run: RunCommand) -> str | None:
    """`git rev-parse HEAD` の結果を返す。git のリポジトリでない・git が無い・打ち切られたときは None。"""
    try:
        result = run(["git", "rev-parse", "HEAD"], cwd=clone, timeout=GIT_TIMEOUT)
    except UpdateFailedError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """`subprocess.run` をタイムアウトつきで呼ぶ（外部コマンドとの境界のアダプター）。"""
    command = " ".join(args)
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            env=None if env is None else dict(env),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise UpdateFailedError(
            f"{command} が上限の {timeout} 秒を過ぎたため打ち切りました"
        ) from exc
    except FileNotFoundError as exc:
        raise UpdateFailedError(f"{command} のコマンドが見つかりません") from exc
    return CommandResult(
        returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
    )


def pull(clone: Path, *, run: RunCommand) -> PullOutcome:
    """commit していない変更を確かめ、上流を取得し、前後を確かめて fast-forward で取り込む。"""
    # 追跡しているファイルに commit していない変更があれば、取得もせずに断る
    status = _git(clone, run, "status", "--porcelain", "--untracked-files=no")
    if status.strip():
        changed = ", ".join(line[3:] for line in status.splitlines() if line.strip())
        raise UpdateFailedError(f"commit していない変更があるため更新しません: {changed}")
    # 上流のブランチが設定されていなければ、取り込む先が無い
    upstream = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=clone,
        timeout=GIT_TIMEOUT,
    )
    if upstream.returncode != 0:
        raise UpdateFailedError(f"{clone} のブランチに上流のブランチが設定されていません")
    _git(clone, run, "fetch")
    before = _git(clone, run, "rev-parse", "HEAD").strip()
    remote = _git(clone, run, "rev-parse", "@{u}").strip()
    # 同じか、クローンが上流より先に進んでいるだけ: 取り込む commit が無い
    if before == remote or _is_ancestor(clone, run, remote, before):
        return PullOutcome(before=before, after=before, pulled=False)
    # HEAD が上流の祖先でない: 分かれているため fast-forward できない
    if not _is_ancestor(clone, run, before, remote):
        raise UpdateFailedError(
            f"クローン（{before}）と上流（{remote}）が分かれていて fast-forward できません"
        )
    _git(clone, run, "merge", "--ff-only", "@{u}")
    after = _git(clone, run, "rev-parse", "HEAD").strip()
    return PullOutcome(before=before, after=after, pulled=True)


def sync_dependencies(clone: Path, env: Mapping[str, str], *, run: RunCommand) -> None:
    """クローンで `uv sync --extra server` を実行する。"""
    uv = env.get(UV_ENV) or shutil.which("uv")
    if uv is None:
        raise UpdateFailedError("uv が見つからないため、依存を入れ直せません")
    args = [uv, "sync", "--extra", "server"]
    result = run(args, cwd=clone, timeout=UV_SYNC_TIMEOUT, env=env)
    if result.returncode != 0:
        raise _failed(args, result)


def plan_migrations(clone: Path, env: Mapping[str, str], *, run: RunCommand) -> list[str]:
    """クローンの `.venv` の Python で `migrate --plan` を実行し、`migrations` を返す。"""
    python = clone / ".venv" / "bin" / "python"
    args = [str(python), "-m", "rule_inject.migrate", "--plan"]
    result = run(args, cwd=clone, timeout=MIGRATE_PLAN_TIMEOUT, env=env)
    # 0 以外（設定がツールより新しい 6 を含む）は失敗にする
    if result.returncode != 0:
        raise _failed(args, result)
    try:
        migrations = json.loads(result.stdout)["migrations"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise UpdateFailedError(
            f"{' '.join(args)} の出力に migrations がありません: {result.stdout.strip()}"
        ) from exc
    return [str(step) for step in migrations]


def _git(clone: Path, run: RunCommand, *args: str) -> str:
    """クローンで git を実行し、0 以外の終了コードは失敗にして標準出力を返す。"""
    command = ["git", *args]
    result = run(command, cwd=clone, timeout=GIT_TIMEOUT)
    if result.returncode != 0:
        raise _failed(command, result)
    return result.stdout


def _is_ancestor(clone: Path, run: RunCommand, ancestor: str, descendant: str) -> bool:
    """ancestor が descendant の祖先か（`git merge-base --is-ancestor` の終了コードが 0 か）。"""
    result = run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=clone,
        timeout=GIT_TIMEOUT,
    )
    return result.returncode == 0


def _failed(args: Sequence[str], result: CommandResult) -> UpdateFailedError:
    """失敗したコマンドを、コマンド・終了コード・標準エラーの末尾を持つ誤りにする。"""
    tail = "\n".join(result.stderr.strip().splitlines()[-STDERR_TAIL_LINES:])
    return UpdateFailedError(
        f"{' '.join(args)} が終了コード {result.returncode} で終わりました: {tail}"
    )
