"""E2E テストが共有する fixture と、実行の進行の記録。

実の Claude Code（`claude -p`）を起動するため、費用がかかる。
`--run-e2e` を付けたときだけ実行し、付けなければ全て skip する。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
# git が管理しているファイルと、管理外で .gitignore にも載らないファイルを、パスを NUL 区切りで返す
GIT_LIST_FILES = ("git", "ls-files", "-co", "--exclude-standard", "-z")
SECONDS_PER_DAY = 86_400
# セッションの記録で、フックが返した案内の文面を載せる行の `attachment.type`
HOOK_CONTEXT_ATTACHMENT_TYPE = "hook_additional_context"
# 文書の MCP サーバーが `get_doc` で返す本文を渡す環境変数
DOCS_BODY_ENV = "E2E_DOCS_BODY"
# 文書の MCP サーバー（`docs`）のスクリプト。`get_doc` と `search_docs` が引数に関わらず決めた本文を返す
DOCS_SERVER_SCRIPT = f'''"""E2E テストが使う、文書を返す stdio の MCP サーバー。"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

server = MCPServer("docs")


@server.tool(name="get_doc")
def get_doc(id: str) -> str:
    """id の文書の本文を返す。"""
    return os.environ["{DOCS_BODY_ENV}"]


@server.tool(name="search_docs")
def search_docs(query: str = "") -> str:
    """検索した文書の本文を返す。"""
    return os.environ["{DOCS_BODY_ENV}"]


if __name__ == "__main__":
    server.run()
'''


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
def log_folder(tmp_path: Path) -> Path:
    """日付ごとのログを置くログのフォルダ。"""
    return tmp_path / "logs"


@pytest.fixture
def e2e_project(tmp_path: Path) -> Path:
    """Claude Code を起動するプロジェクトのフォルダ（対象のファイルもここへ置く）。"""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    return project


@pytest.fixture
def configure_env(e2e_project: Path, tmp_path: Path) -> Callable[..., None]:
    """プロジェクトの設定の `env` に、索引の無い設定フォルダと空の状態フォルダを指す環境変数と、渡した環境変数を書く。"""

    def _configure(env: Mapping[str, str] | None = None) -> None:
        """env を `XDG_CONFIG_HOME` と `XDG_STATE_HOME` の隔離に重ねて、プロジェクトの設定の `env` に書く。"""
        # 利用者の設定（~/.claude）は読み込ませないため、`env` はプロジェクトの設定に書く
        merged = {
            # ユーザーの既定の索引が実際の設定フォルダの索引を読まないよう、索引の無いフォルダを指す
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            # 既定のログのフォルダが実際の状態フォルダに書かれないよう、空のフォルダを指す
            "XDG_STATE_HOME": str(tmp_path / "xdg_state"),
        }
        merged.update(env or {})
        (e2e_project / ".claude" / "settings.json").write_text(
            json.dumps({"env": merged}, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return _configure


@pytest.fixture
def configure_index(
    e2e_project: Path,
    tmp_path: Path,
    state_dir: Path,
    log_folder: Path,
    configure_env: Callable[..., None],
) -> Callable[..., None]:
    """設定ファイルに記録フォルダ・ログのフォルダと、起動したプロジェクトに当たる `projects` の要素の索引を書き、`RULE_INJECT_CONFIG` でその設定ファイルを指す。"""

    def _configure(index: Path | str, *, extra_env: Mapping[str, str] | None = None) -> None:
        """index を起動したプロジェクトに当たる `projects` の要素の `indexes` に書き、extra_env を `env` に足す。"""
        lines = [
            "global:",
            f'  state_dir: "{state_dir}"',
            f'  log_dir: "{log_folder}"',
            "projects:",
            f'  - match: "{e2e_project}"',
            "    indexes:",
            f'      - "{index}"',
        ]
        config = tmp_path / "config" / "settings.yaml"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text("\n".join(lines) + "\n", encoding="utf-8")
        configure_env({"RULE_INJECT_CONFIG": str(config), **(extra_env or {})})

    return _configure


@pytest.fixture(scope="session")
def plugin_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """プラグインのファイルを Linux 側の一時フォルダへ写し、そのフォルダを返す（実行ごとに 1 回）。"""
    destination = tmp_path_factory.mktemp("plugin")
    listed = subprocess.run(
        GIT_LIST_FILES,
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    # 日本語のパスを含むため、クォートされない NUL 区切りの出力を分ける
    for relative in filter(None, listed.split("\0")):
        source = PROJECT_ROOT / relative
        # フォルダの行と、作業ツリーから消えているファイルは写さない
        if not source.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination


@pytest.fixture
def run_claude(e2e_project: Path, plugin_dir: Path) -> Callable[..., ClaudeRun]:
    """利用者の設定を読み込ませずに `claude -p` を 1 回動かし、その結果を返す factory。"""

    def _run(
        prompt: str,
        *,
        allow: Sequence[str] = (),
        deny: Sequence[str] = (),
        resume: str | None = None,
        max_turns: int | None = DEFAULT_MAX_TURNS,
        mcp_config: Path | None = None,
    ) -> ClaudeRun:
        """プラグインだけを読み込み、プロジェクトの設定だけを使って prompt を実行する。mcp_config があれば、その MCP サーバーも渡す。"""
        binary = os.environ.get(CLAUDE_BIN_ENV) or shutil.which("claude")
        if binary is None:
            pytest.skip("claude が PATH に無い")
        # 利用者の設定（~/.claude）のフック・プラグイン・MCP サーバーを読み込ませない。--bare は API の課金になるため使わない
        command = [
            binary,
            "-p",
            prompt,
            "--plugin-dir",
            str(plugin_dir),
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
        if mcp_config is not None:
            command += ["--mcp-config", str(mcp_config)]
        if os.environ.get(CLAUDE_MODEL_ENV):
            command += ["--model", os.environ[CLAUDE_MODEL_ENV]]
        env = {
            name: value for name, value in os.environ.items() if not name.startswith("RULE_INJECT_")
        }
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


def _transcript_lines(session_id: str) -> list[str]:
    """~/.claude（か CLAUDE_CONFIG_DIR）の下から、session_id の記録を探して、空でない行を返す。"""
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    path = next(config_dir.glob(f"projects/*/{session_id}.jsonl"))
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture
def transcript_text() -> Callable[[str], str]:
    """セッションの記録（transcript）の全文を、日本語をエスケープしない文字列にして返す。"""

    def _read(session_id: str) -> str:
        """session_id の記録の各行を、日本語をエスケープしない文字列にして連ねる。"""
        return "\n".join(
            json.dumps(json.loads(line), ensure_ascii=False)
            for line in _transcript_lines(session_id)
        )

    return _read


@pytest.fixture
def guidance_count() -> Callable[[str, str], int]:
    """セッションの記録のうち、フックの案内の行に文面が載っている行の数を返す。"""

    def _count(session_id: str, snippet: str) -> int:
        """`hook_additional_context` の行のうち、`attachment.content` が snippet を含む行を数える。"""
        count = 0
        for line in _transcript_lines(session_id):
            attachment = json.loads(line).get("attachment")
            # 案内の行（attachment.type が hook_additional_context）だけを数える。`rendered[].content` の写しは見ない
            if not isinstance(attachment, dict):
                continue
            if attachment.get("type") != HOOK_CONTEXT_ATTACHMENT_TYPE:
                continue
            content = attachment["content"]
            # content は文字列の配列。文字列のときはその文字列で判定する
            texts = [content] if isinstance(content, str) else content
            if any(snippet in text for text in texts):
                count += 1
        return count

    return _count


@pytest.fixture
def record_locations(state_dir: Path) -> Callable[[str], list[str]]:
    """そのセッションの既読の記録の行（`{場所}\\t{ハッシュ}`）を返す（記録ファイルが無ければ空）。"""

    def _read(session_id: str) -> list[str]:
        """記録ファイルの行を返す。"""
        path = state_dir / f"{session_id}.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    return _read


@pytest.fixture
def guided_locations(state_dir: Path) -> Callable[[str], list[str]]:
    """そのセッションの案内済みの記録の場所を返す（記録ファイルが無ければ空）。"""

    def _read(session_id: str) -> list[str]:
        """案内済みの記録ファイルの行を返す。"""
        path = state_dir / f"{session_id}.guided.txt"
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    return _read


@pytest.fixture
def record_history(state_dir: Path) -> Callable[[str], list[dict[str, Any]]]:
    """そのセッションの既読の履歴の行を返す（履歴ファイルが無ければ空）。"""

    def _read(session_id: str) -> list[dict[str, Any]]:
        """履歴ファイルの各行を JSON として読む。"""
        path = state_dir / f"{session_id}.history.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    return _read


@pytest.fixture
def docs_mcp_config(tmp_path: Path) -> Callable[[str], Path]:
    """`get_doc` と `search_docs` が決めた本文を返す stdio の MCP サーバー `docs` を置き、`--mcp-config` に渡す設定のファイルを返す factory。"""

    def _make(body: str) -> Path:
        """body を返す `get_doc`（引数 `id`）と `search_docs`（引数 `query`）を持つサーバーのスクリプトと設定を tmp_path の下に書く。"""
        script = tmp_path / "docs_server.py"
        script.write_text(DOCS_SERVER_SCRIPT, encoding="utf-8")
        config = tmp_path / "docs_mcp.json"
        server = {
            "type": "stdio",
            "command": sys.executable,
            "args": [str(script)],
            "env": {DOCS_BODY_ENV: body},
        }
        config.write_text(json.dumps({"mcpServers": {"docs": server}}), encoding="utf-8")
        return config

    return _make


@pytest.fixture
def write_aged_record(state_dir: Path) -> Callable[..., Path]:
    """最終更新を現在から指定の日数前に戻した記録ファイル（既読か案内済み）を置く factory。"""

    def _write(record_session_id: str, age_days: int, *, suffix: str = ".txt") -> Path:
        """record_session_id の記録ファイル（suffix の名前）を置き、最終更新を age_days 日前にして返す。"""
        path = state_dir / f"{record_session_id}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("/r/a.md\n", encoding="utf-8")
        modified = time.time() - age_days * SECONDS_PER_DAY
        os.utime(path, (modified, modified))
        return path

    return _write


@pytest.fixture
def write_dated_log(log_folder: Path) -> Callable[[date], Path]:
    """日付を名前に持つログのファイルを、ログのフォルダに置く factory。"""

    def _write(day: date) -> Path:
        """day の日付の `{yyyymmdd}_rule-inject.log` をログのフォルダに置いて返す。"""
        path = log_folder / f"{day:%Y%m%d}_rule-inject.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    return _write


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

    def _make(*entries: Mapping[str, Any], to: str = "index.yaml") -> Path:
        """各エントリの rule・paths・on・read_by から索引を組み立て、tmp_path の下の to に書く。"""
        lines = ["rules:"]
        for entry in entries:
            lines.append(f"  - rule: {entry['rule']}")
            # 書かれた条件だけをエントリに足す
            if entry.get("paths"):
                lines.append("    paths:")
                lines.extend(f'      - "{value}"' for value in entry["paths"])
            if entry.get("on") is not None:
                lines.append(f"    on: [{', '.join(entry['on'])}]")
            # 既読にする呼び出しは、`tools` のリストと任意の `args` のマップを持つ要素のブロックのリストで書く
            if entry.get("read_by"):
                lines.append("    read_by:")
                for condition in entry["read_by"]:
                    lines.append("      - tools:")
                    lines.extend(f'          - "{pattern}"' for pattern in condition["tools"])
                    if condition.get("args"):
                        lines.append("        args:")
                        for arg_key, patterns in condition["args"].items():
                            lines.append(f"          {arg_key}:")
                            lines.extend(f'            - "{pattern}"' for pattern in patterns)
        path = tmp_path / to
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _make
