"""E2E テストが共有する fixture と、実行の進行の記録。

実の Claude Code（`claude -p`）を起動するため、費用がかかる。
`--run-e2e` を付けたときだけ実行し、付けなければ全て skip する。
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

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
# 常駐の MCP サーバーの待ち受けのアドレスと、接続・起動・停止の待ち時間
SERVER_HOST = "127.0.0.1"
# 1 回の起動で、標準エラーに待ち受けの開始の行が出るまでを待つ上限
SERVER_START_TIMEOUT_SEC = 51
# 待ち受けに失敗して子プロセスが終わったとき、別の空いているポートで起動し直す回数の上限
SERVER_START_ATTEMPTS = 5
SERVER_STOP_TIMEOUT_SEC = 20
SERVER_CALL_TIMEOUT_SEC = 60
SERVER_POLL_INTERVAL_SEC = 0.1
# 常駐の MCP サーバーを `claude` へ登録・渡すときの名前
MCP_SERVER_NAME = "rule-inject"
# `/proc/net/tcp` の状態が LISTEN のときの値
LISTEN_STATE = "0A"
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
    """費用のかかる E2E テストを実行する `--run-e2e` を追加する。"""
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
        """index を起動したプロジェクトに当たる `projects` の要素の `indexes` に書き、extra_env を `env` に追加する。"""
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
    """プラグインのファイルを Linux 側の一時フォルダへコピーし、そのフォルダを返す（実行ごとに 1 回）。"""
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
        # フォルダの行と、作業ツリーから削除されたファイルはコピーしない
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
            # 案内の行（attachment.type が hook_additional_context）だけを数える。`rendered[].content` のコピーは見ない
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
        """prefix に一意の文字列を追加して返す。"""
        return f"{prefix}-{uuid4().hex[:8]}"

    return _make


# 偽の dev-docs が返す応答の JSON を渡す環境変数と、待ち受けるポートを渡す環境変数
DEV_DOCS_BODY_ENV = "E2E_DEV_DOCS_BODY"
DEV_DOCS_PORT_ENV = "E2E_DEV_DOCS_PORT"
# 偽の dev-docs のスクリプト。`search_docs` が引数に関わらず決めた応答の JSON を返す Streamable HTTP の MCP サーバー
DEV_DOCS_SERVER_SCRIPT = f'''"""E2E テストが使う、使われているタグを返す偽の dev-docs。"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

server = MCPServer("dev-docs")


@server.tool(name="search_docs")
def search_docs(
    source: str = "", group_by: str = "", format: str = "markdown", cwd: str = ""
) -> str:
    """使われているタグを件数つきで返す。"""
    return os.environ["{DEV_DOCS_BODY_ENV}"]


if __name__ == "__main__":
    server.run("streamable-http", host="{SERVER_HOST}", port=int(os.environ["{DEV_DOCS_PORT_ENV}"]))
'''


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
        """各エントリの rule・paths・on・enabled・read_by から索引を組み立て、tmp_path の下の to に書く。"""
        lines = ["rules:"]
        for entry in entries:
            lines.append(f"  - rule: {entry['rule']}")
            # 書かれた条件だけをエントリに追加する
            if entry.get("paths"):
                lines.append("    paths:")
                lines.extend(f'      - "{value}"' for value in entry["paths"])
            if entry.get("on") is not None:
                lines.append(f"    on: [{', '.join(entry['on'])}]")
            # 無効のエントリは `enabled: false` で書く
            if entry.get("enabled") is not None:
                lines.append(f"    enabled: {str(entry['enabled']).lower()}")
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


@dataclass
class ResidentServer:
    """起動した常駐の MCP サーバーの子プロセスと、接続先・呼び出しの手段。"""

    port: int
    process: subprocess.Popen[bytes]
    stderr_path: Path

    @property
    def url(self) -> str:
        """MCP のエンドポイント。"""
        return f"http://{SERVER_HOST}:{self.port}/mcp"

    def stderr_text(self) -> str:
        """子プロセスの標準エラーを読む。"""
        return self.stderr_path.read_text(encoding="utf-8")

    def call(self, name: str, **arguments: Any) -> CallToolResult:
        """MCP の Python SDK のクライアント（Streamable HTTP）でツールを 1 回呼ぶ。"""

        async def _call() -> CallToolResult:
            """接続して初期化してから、ツールを呼ぶ。"""
            async with (
                streamable_http_client(self.url) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                return await session.call_tool(name, arguments)

        return asyncio.run(asyncio.wait_for(_call(), SERVER_CALL_TIMEOUT_SEC))


def _free_port() -> int:
    """ポート 0 で待ち受けて、割り当てられたポートを返す（すぐ閉じる）。

    閉じてから子プロセスが待ち受けるまでの間に他のプロセスが同じポートを取ることがあるため、
    この番号で起動する側は `_launch` で起動を確かめ、失敗したら別の番号で起動し直す。
    """
    with socket.create_server((SERVER_HOST, 0)) as probe:
        return int(probe.getsockname()[1])


def _ready_line(port: int) -> str:
    """uvicorn が待ち受けを始めたときに標準エラーへ書く行（`port` で待ち受けたときだけ出る）。"""
    return f"Uvicorn running on http://{SERVER_HOST}:{port}"


def _wait_ready(process: subprocess.Popen[bytes], stderr_path: Path, port: int) -> bool:
    """標準エラーに `port` の待ち受けの開始の行が出るまで待つ。

    先に子プロセスが終わったときは、待ち受けに失敗したとして False を返す。
    時間を超えたときは子プロセスを止めて失敗にする。
    """
    deadline = time.monotonic() + SERVER_START_TIMEOUT_SEC
    while True:
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        # 行が出ている: このポートで待ち受けている（他のプロセスの待ち受けでは出ない）
        if _ready_line(port) in stderr:
            return True
        # 行が出ないまま終わった: 待ち受けに失敗した（ポートを他のプロセスに取られた等）
        if process.poll() is not None:
            return False
        # 終わらず行も出ない: 時間の上限まで待ち、超えたら止めて失敗にする
        if time.monotonic() > deadline:
            process.kill()
            process.wait()
            pytest.fail(f"{SERVER_START_TIMEOUT_SEC} 秒で待ち受けなかった: {stderr}")
        time.sleep(SERVER_POLL_INTERVAL_SEC)


def _launch(
    spawn: Callable[[int, int], tuple[subprocess.Popen[bytes], Path]],
) -> tuple[int, subprocess.Popen[bytes], Path]:
    """空いているポートで子プロセスを起動して待ち受けるまで待ち、失敗したら別のポートで起動し直す。

    spawn は (ポート, 何回目か) を受けて起動し、子プロセスと標準エラーのファイルを返す。
    待ち受けたポート・子プロセス・標準エラーのファイルを返す。`SERVER_START_ATTEMPTS` 回とも失敗したら失敗にする。
    """
    stderr = ""
    for attempt in range(SERVER_START_ATTEMPTS):
        port = _free_port()
        process, stderr_path = spawn(port, attempt)
        if _wait_ready(process, stderr_path, port):
            return port, process, stderr_path
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    pytest.fail(f"{SERVER_START_ATTEMPTS} 回起動し直しても待ち受けなかった: {stderr}")


def _listening_addresses(port: int) -> set[str]:
    """ポートで待ち受けているソケットのアドレス（IPv4 は 16 進、IPv6 は `v6:` を付けた 16 進）を返す。"""
    addresses: set[str] = set()
    for table, prefix in (("/proc/net/tcp", ""), ("/proc/net/tcp6", "v6:")):
        for line in Path(table).read_text(encoding="utf-8").splitlines()[1:]:
            fields = line.split()
            address, local_port = fields[1].rsplit(":", 1)
            if fields[3] == LISTEN_STATE and int(local_port, 16) == port:
                addresses.add(prefix + address)
    return addresses


def _stop_server(server: ResidentServer) -> None:
    """動いているサーバーを SIGTERM で止める。止まらなければ強制終了する。"""
    if server.process.poll() is not None:
        return
    server.process.send_signal(signal.SIGTERM)
    try:
        server.process.wait(timeout=SERVER_STOP_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        server.process.kill()
        server.process.wait()


@pytest.fixture
def addresses_listening() -> Callable[[int], set[str]]:
    """ポートで待ち受けているソケットのアドレスを返す関数。"""
    return _listening_addresses


@pytest.fixture
def server_config_path(tmp_path: Path) -> Path:
    """フックとサーバーが読む設定ファイルの場所（`RULE_INJECT_CONFIG` が指す）。"""
    return tmp_path / "config" / "settings.yaml"


@pytest.fixture
def write_server_config(
    e2e_project: Path,
    state_dir: Path,
    log_folder: Path,
    server_config_path: Path,
    configure_env: Callable[..., None],
) -> Callable[..., Path]:
    """待ち受けのポート・`global.indexes`・起動したプロジェクトに当たる `projects` の要素の索引を書いた設定ファイルを置き、`RULE_INJECT_CONFIG` でそれを指す。"""

    def _write(
        port: int,
        *,
        project_indexes: Sequence[Path] = (),
        global_indexes: Sequence[Path] = (),
        dev_docs_url: str | None = None,
    ) -> Path:
        """設定ファイルを書き、プロジェクトの設定の `env` にそのパスを置く。dev_docs_url があれば `global.dev_docs_url` に書く。"""
        lines = [
            "global:",
            f'  state_dir: "{state_dir}"',
            f'  log_dir: "{log_folder}"',
            f"  server_port: {port}",
        ]
        if dev_docs_url is not None:
            lines.append(f"  dev_docs_url: {dev_docs_url}")
        if global_indexes:
            lines.append("  indexes:")
            lines.extend(f'    - "{index}"' for index in global_indexes)
        if project_indexes:
            lines.extend(["projects:", f'  - match: "{e2e_project}"', "    indexes:"])
            lines.extend(f'      - "{index}"' for index in project_indexes)
        server_config_path.parent.mkdir(parents=True, exist_ok=True)
        server_config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        configure_env({"RULE_INJECT_CONFIG": str(server_config_path)})
        return server_config_path

    return _write


@pytest.fixture
def resident_server(
    tmp_path: Path, server_config_path: Path
) -> Iterator[Callable[..., ResidentServer]]:
    """ローカルのクローンから `python -m rule_inject.server` を子プロセスとして起動する factory。終わったら止める。"""
    started: list[ResidentServer] = []

    def _spawn_at(
        configure: Callable[[int], object], port: int, attempt: int
    ) -> tuple[subprocess.Popen[bytes], Path]:
        """port を configure に渡して設定ファイルを書き、それを指して起動する。"""
        server_config_path.parent.mkdir(parents=True, exist_ok=True)
        configure(port)
        env = {
            name: value for name, value in os.environ.items() if not name.startswith("RULE_INJECT_")
        }
        env["RULE_INJECT_CONFIG"] = str(server_config_path)
        env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
        env["XDG_STATE_HOME"] = str(tmp_path / "xdg_state")
        stderr_path = tmp_path / f"server-{len(started)}-{attempt}.stderr"
        with stderr_path.open("wb") as stderr_file:
            process = subprocess.Popen(
                [sys.executable, "-m", "rule_inject.server"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
            )
        return process, stderr_path

    def _start(configure: Callable[[int], object], *, wait_ready: bool = True) -> ResidentServer:
        """空いているポートを configure に渡して設定ファイルを書かせ、起動する。

        wait_ready なら待ち受けるまで待ち、待ち受けに失敗したら別のポートで起動し直す。
        wait_ready でなければ 1 回だけ起動して待たない（起動に失敗する確かめに使う）。
        """
        if wait_ready:
            port, process, stderr_path = _launch(
                lambda port, attempt: _spawn_at(configure, port, attempt)
            )
        else:
            port = _free_port()
            process, stderr_path = _spawn_at(configure, port, 0)
        server = ResidentServer(port=port, process=process, stderr_path=stderr_path)
        started.append(server)
        return server

    yield _start
    for server in started:
        _stop_server(server)


@pytest.fixture
def stop_server() -> Callable[[ResidentServer], None]:
    """サーバーを SIGTERM で止めて終わりを待つ関数。"""
    return _stop_server


@pytest.fixture
def serve(
    e2e_project: Path,
    write_server_config: Callable[..., Path],
    resident_server: Callable[..., ResidentServer],
) -> Callable[..., ResidentServer]:
    """空いているポートを設定ファイルに書き、常駐の MCP サーバーを起動する factory。"""

    def _serve(
        *project_indexes: Path,
        global_indexes: Sequence[Path] = (),
        dev_docs_url: str | None = None,
    ) -> ResidentServer:
        """project_indexes を起動したプロジェクトに当たる要素の索引に、global_indexes を `global.indexes` に、dev_docs_url を `global.dev_docs_url` に置いて起動する。"""
        return resident_server(
            lambda port: write_server_config(
                port,
                project_indexes=project_indexes,
                global_indexes=global_indexes,
                dev_docs_url=dev_docs_url,
            )
        )

    return _serve


@pytest.fixture
def start_dev_docs(tmp_path: Path) -> Iterator[Callable[[Mapping[str, Any]], str]]:
    """`search_docs` が決めた応答を返す偽の dev-docs を子プロセスとして立て、その接続先を返す factory。終わったら止める。"""
    processes: list[subprocess.Popen[bytes]] = []

    def _start(response: Mapping[str, Any]) -> str:
        """response の JSON を返す偽の dev-docs を空いているポートで立て、待ち受けるまで待つ（失敗したら別のポートで立て直す）。"""
        script = tmp_path / "dev_docs_server.py"
        script.write_text(DEV_DOCS_SERVER_SCRIPT, encoding="utf-8")

        def _spawn_at(port: int, attempt: int) -> tuple[subprocess.Popen[bytes], Path]:
            """port で偽の dev-docs を起動する（標準エラーはファイルへ書く）。"""
            env = dict(os.environ)
            env[DEV_DOCS_BODY_ENV] = json.dumps(response, ensure_ascii=False)
            env[DEV_DOCS_PORT_ENV] = str(port)
            stderr_path = tmp_path / f"dev-docs-{len(processes)}-{attempt}.stderr"
            with stderr_path.open("wb") as stderr_file:
                process = subprocess.Popen(
                    [sys.executable, str(script)],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_file,
                )
            processes.append(process)
            return process, stderr_path

        port, _, _ = _launch(_spawn_at)
        return f"http://{SERVER_HOST}:{port}/mcp"

    yield _start
    for process in processes:
        process.terminate()
        try:
            process.wait(timeout=SERVER_STOP_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture
def server_mcp_config(tmp_path: Path) -> Callable[[ResidentServer], Path]:
    """常駐の MCP サーバーを HTTP の接続先として `--mcp-config` に渡す設定のファイルを置く関数。"""

    def _make(server: ResidentServer) -> Path:
        """`claude -p --mcp-config` に渡す JSON を書いて、そのパスを返す。"""
        config = tmp_path / "resident_mcp.json"
        body = {"mcpServers": {MCP_SERVER_NAME: {"type": "http", "url": server.url}}}
        config.write_text(json.dumps(body), encoding="utf-8")
        return config

    return _make


@pytest.fixture
def run_claude_cli(
    e2e_project: Path, tmp_path: Path
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """利用者の設定（`~/.claude`）を使わず、一時フォルダを `CLAUDE_CONFIG_DIR` にして `claude` の CLI のコマンドを 1 回実行する関数。"""

    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        """`claude {args}` を実行して結果を返す（API は呼ばない `mcp add` と `mcp list` に使う）。"""
        binary = os.environ.get(CLAUDE_BIN_ENV) or shutil.which("claude")
        if binary is None:
            pytest.skip("claude が PATH に無い")
        env = {
            name: value for name, value in os.environ.items() if not name.startswith("RULE_INJECT_")
        }
        env["CLAUDE_CONFIG_DIR"] = str(tmp_path / "claude_config")
        return subprocess.run(
            [binary, *args],
            cwd=e2e_project,
            env=env,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SEC,
            check=False,
        )

    return _run


@pytest.fixture
def make_text_file(tmp_path: Path) -> Callable[..., Path]:
    """書いたとおりの内容のファイル（コメント・引用符つきの索引など）を tmp_path の下へ置く factory。"""

    def _make(name: str, text: str) -> Path:
        """tmp_path の下の name に text を書いて返す。"""
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _make


@pytest.fixture
def tool_text() -> Callable[[CallToolResult], str]:
    """ツールの結果の text をつなげて返す関数。"""

    def _text(result: CallToolResult) -> str:
        """結果の content の text をつなげる。"""
        return "\n".join(getattr(content, "text", "") for content in result.content)

    return _text
