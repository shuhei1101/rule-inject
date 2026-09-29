"""E2E テストが共有する fixture と、実行の進行の記録。

実の Claude Code（`claude -p`）を起動するため、費用がかかる。
`--run-e2e` を付けたときだけ実行し、付けなければ全て skip する。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

E2E_OPTION = "--run-e2e"
E2E_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = E2E_DIR.parents[1]
# 進行の記録を置くフォルダ（`results.jsonl` / `done` / `release_head` / `abort` を持つ）
RUN_DIR_ENV = "E2E_RUN_DIR"
CLAUDE_BIN_ENV = "E2E_CLAUDE_BIN"
CLAUDE_MODEL_ENV = "E2E_CLAUDE_MODEL"
CLAUDE_TIMEOUT_SEC = 900
DEFAULT_MAX_TURNS = 5
# MCP サーバーの起動の待ち時間（ミリ秒）。入れた直後の最初の起動は uv が依存を取得する分だけ遅い
MCP_TIMEOUT_MS = "60000"
READ_RULES_TOOL = "mcp__plugin_rule-inject_rule-inject__read_rules"


def pytest_addoption(parser: pytest.Parser) -> None:
    """費用のかかる E2E テストを実行する `--run-e2e` を足す。"""
    parser.addoption(
        E2E_OPTION,
        action="store_true",
        default=False,
        help="実の Claude Code を起動する E2E テストを実行する（費用がかかる）",
    )


def _is_e2e(path: Path) -> bool:
    """このフォルダの下のテストかを返す。"""
    return E2E_DIR in path.parents


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """`--run-e2e` が無いとき、このフォルダのテストを全て skip する。"""
    if config.getoption(E2E_OPTION, default=False):
        return
    skip = pytest.mark.skip(reason=f"費用がかかるため {E2E_OPTION} を付けたときだけ実行する")
    for item in items:
        if _is_e2e(item.path):
            item.add_marker(skip)


def _run_dir() -> Path | None:
    """進行の記録を置くフォルダ（環境変数が無ければ None）を返す。"""
    configured = os.environ.get(RUN_DIR_ENV)
    return Path(configured) if configured else None


def pytest_sessionstart(session: pytest.Session) -> None:
    """進行の記録のフォルダがあれば、実行するリリースの commit を `release_head` に書く。"""
    run_dir = _run_dir()
    if run_dir is None:
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (run_dir / "release_head").write_text(head + "\n", encoding="utf-8")


def pytest_runtest_setup(item: pytest.Item) -> None:
    """`abort` の合図ファイルがあれば、次のシナリオを始めずに実行を止める。"""
    run_dir = _run_dir()
    if run_dir is not None and _is_e2e(item.path) and (run_dir / "abort").exists():
        pytest.exit(f"{run_dir / 'abort'} があるため、実行を中断する", returncode=2)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """シナリオの結果を 1 行ずつ `results.jsonl` へ追記する。"""
    run_dir = _run_dir()
    is_result = report.when == "call" or (report.when == "setup" and report.outcome != "passed")
    if run_dir is None or not is_result or not report.nodeid.startswith("tests/e2e/"):
        return
    line = json.dumps(
        {
            "time": datetime.now(UTC).isoformat(),
            "nodeid": report.nodeid,
            "outcome": report.outcome,
            "duration_sec": round(report.duration, 1),
        },
        ensure_ascii=False,
    )
    with (run_dir / "results.jsonl").open("a", encoding="utf-8") as results:
        results.write(line + "\n")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """進行の記録のフォルダがあれば、実行が終わったことを `done` に書く（中断も含む）。"""
    run_dir = _run_dir()
    if run_dir is not None:
        (run_dir / "done").write_text(f"{exitstatus}\n", encoding="utf-8")


def _tool_result_text(block: Mapping[str, Any]) -> str:
    """tool_result のブロックの本文を文字列にする。"""
    content = block.get("content", "")
    if isinstance(content, str):
        return content
    return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaudeRun:
    """`claude -p` 1 回の結果。"""

    session_id: str
    result: dict[str, Any]
    events: list[dict[str, Any]]

    @property
    def answer(self) -> str:
        """最後の応答の文面。"""
        return str(self.result.get("result", ""))

    @property
    def denied_tools(self) -> list[str]:
        """`permission_denials` に載ったツール名。"""
        return [denial["tool_name"] for denial in self.result.get("permission_denials", [])]

    @property
    def tool_results(self) -> dict[str, str]:
        """tool_use_id ごとの、ツールの結果の文面。"""
        results: dict[str, str] = {}
        for event in self.events:
            if event.get("type") != "user":
                continue
            content = event.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    results[block["tool_use_id"]] = _tool_result_text(block)
        return results

    @property
    def denial_reasons(self) -> list[str]:
        """止められたツールの呼び出しごとの、止めた理由の文面。"""
        results = self.tool_results
        return [
            results.get(denial["tool_use_id"], "")
            for denial in self.result.get("permission_denials", [])
        ]


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """既読の記録を置く記録フォルダ。"""
    return tmp_path / "state"


@pytest.fixture
def e2e_project(tmp_path: Path) -> Path:
    """Claude Code を起動するプロジェクトのフォルダ（対象のファイルもここへ置く）。"""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    return project


@pytest.fixture
def configure_index(e2e_project: Path, state_dir: Path) -> Callable[[Path | str], None]:
    """プロジェクトの設定の `env` に、索引と記録フォルダを書く。"""

    def _configure(index: Path | str) -> None:
        """index をプロジェクト用の索引として指す。"""
        settings = {
            "env": {
                "RULE_INJECT_INDEXES_PROJECT": str(index),
                "RULE_INJECT_STATE_DIR": str(state_dir),
            }
        }
        (e2e_project / ".claude" / "settings.json").write_text(
            json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return _configure


@pytest.fixture
def run_claude(e2e_project: Path) -> Callable[..., ClaudeRun]:
    """利用者の設定を読み込ませずに `claude -p` を 1 回動かし、その結果を返す factory。"""

    def _run(
        prompt: str,
        *,
        allow: Sequence[str] = (),
        deny: Sequence[str] = (),
        resume: str | None = None,
        max_turns: int | None = DEFAULT_MAX_TURNS,
    ) -> ClaudeRun:
        """プラグインだけを読み込み、プロジェクトの設定だけを使って prompt を実行する。"""
        binary = os.environ.get(CLAUDE_BIN_ENV) or shutil.which("claude")
        if binary is None:
            pytest.skip("claude が PATH に無い")
        # 利用者の設定（~/.claude）のフック・プラグイン・MCP サーバーを読み込ませない。--bare は API の課金になるため使わない
        command = [
            binary,
            "-p",
            prompt,
            "--plugin-dir",
            str(PROJECT_ROOT),
            "--setting-sources",
            "project",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if max_turns is not None:
            command += ["--max-turns", str(max_turns)]
        if allow:
            command += ["--allowedTools", ",".join(allow)]
        if deny:
            command += ["--disallowedTools", ",".join(deny)]
        if resume is not None:
            command += ["--resume", resume]
        if os.environ.get(CLAUDE_MODEL_ENV):
            command += ["--model", os.environ[CLAUDE_MODEL_ENV]]
        env = {
            name: value for name, value in os.environ.items() if not name.startswith("RULE_INJECT_")
        }
        env.setdefault("MCP_TIMEOUT", MCP_TIMEOUT_MS)
        completed = subprocess.run(
            command,
            cwd=e2e_project,
            env=env,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SEC,
            check=False,
        )
        events = [
            json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")
        ]
        results = [event for event in events if event.get("type") == "result"]
        if not results:
            pytest.fail(
                f"claude の結果が無い（終了コード {completed.returncode}）: {completed.stderr}"
            )
        return ClaudeRun(session_id=results[-1]["session_id"], result=results[-1], events=events)

    return _run


@pytest.fixture
def transcript_text() -> Callable[[str], str]:
    """セッションの記録（transcript）の全文を、日本語をエスケープしない文字列にして返す。"""

    def _read(session_id: str) -> str:
        """~/.claude（か CLAUDE_CONFIG_DIR）の下から、session_id の記録を探して読む。"""
        config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        path = next(config_dir.glob(f"projects/*/{session_id}.jsonl"))
        lines = path.read_text(encoding="utf-8").splitlines()
        return "\n".join(json.dumps(json.loads(line), ensure_ascii=False) for line in lines if line)

    return _read


@pytest.fixture
def record_locations(state_dir: Path) -> Callable[[str], list[str]]:
    """そのセッションの既読の記録の場所を返す（記録ファイルが無ければ空）。"""

    def _read(session_id: str) -> list[str]:
        """記録ファイルの行を返す。"""
        path = state_dir / f"{session_id}.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    return _read


@pytest.fixture
def marker() -> Callable[[str], str]:
    """応答に出たかで見分ける、実行ごとに一意の文字列を作る。"""

    def _make(prefix: str) -> str:
        """prefix に一意の文字列を足して返す。"""
        return f"{prefix}-{uuid4().hex[:8]}"

    return _make


@pytest.fixture
def make_rule(tmp_path: Path) -> Callable[..., Path]:
    """ローカルのルールの本文（Markdown）を置く factory。"""

    def _make(name: str, body: str) -> Path:
        """tmp_path/rules の下に name のファイルを置く。"""
        path = tmp_path / "rules" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    return _make


@pytest.fixture
def make_index(tmp_path: Path) -> Callable[..., Path]:
    """エントリの dict を並べた索引の YAML を置き、そのパスを返す factory。"""

    def _make(*entries: Mapping[str, Any]) -> Path:
        """各エントリの rule・paths・on から索引を組み立てて書く。"""
        lines = ["rules:"]
        for entry in entries:
            lines.append(f"  - rule: {entry['rule']}")
            # 書かれた条件だけをエントリに足す
            if entry.get("paths"):
                lines.append("    paths:")
                lines.extend(f'      - "{value}"' for value in entry["paths"])
            if entry.get("on") is not None:
                lines.append(f"    on: [{', '.join(entry['on'])}]")
        path = tmp_path / "index.yaml"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _make
