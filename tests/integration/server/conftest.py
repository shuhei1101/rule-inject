"""サーバーの結合テストが共有する fixture。サーバーは子プロセスとして起動し、MCP の Streamable HTTP のクライアントで呼ぶ。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

HOST = "127.0.0.1"
START_TIMEOUT_SEC = 30
STOP_TIMEOUT_SEC = 15
CALL_TIMEOUT_SEC = 30
POLL_INTERVAL_SEC = 0.1
# `/proc/net/tcp` の状態が LISTEN のときの値と、127.0.0.1 の 16 進の表記
LISTEN_STATE = "0A"
LOOPBACK_HEX = "0100007F"


@dataclass
class RunningServer:
    """起動したサーバーの子プロセスと、接続先・呼び出しの手段。"""

    port: int
    process: subprocess.Popen[bytes]
    config_path: Path
    stderr_path: Path

    @property
    def url(self) -> str:
        """MCP のエンドポイント。"""
        return f"http://{HOST}:{self.port}/mcp"

    def stderr_text(self) -> str:
        """子プロセスの標準エラーを読む。"""
        return self.stderr_path.read_text(encoding="utf-8")

    def call(self, name: str, **arguments: Any) -> CallToolResult:
        """ツールを 1 回呼ぶ（接続して初期化してから呼び、閉じる）。"""

        async def _call() -> CallToolResult:
            """接続してツールを呼ぶ。"""
            async with (
                streamable_http_client(self.url) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                return await session.call_tool(name, arguments)

        return asyncio.run(asyncio.wait_for(_call(), CALL_TIMEOUT_SEC))

    def tool_names(self) -> list[str]:
        """ツールの一覧の名前を返す。"""

        async def _list() -> list[str]:
            """接続してツールの一覧を取る。"""
            async with (
                streamable_http_client(self.url) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                return [tool.name for tool in (await session.list_tools()).tools]

        return asyncio.run(asyncio.wait_for(_list(), CALL_TIMEOUT_SEC))


def is_listening(port: int) -> bool:
    """127.0.0.1 のポートへ接続できるか。"""
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def listening_addresses(port: int) -> set[str]:
    """ポートで待ち受けているソケットのアドレス（IPv4 は 16 進、IPv6 は `v6:` を付けた 16 進）を返す。"""
    addresses: set[str] = set()
    for table, prefix in (("/proc/net/tcp", ""), ("/proc/net/tcp6", "v6:")):
        for line in Path(table).read_text(encoding="utf-8").splitlines()[1:]:
            fields = line.split()
            local, state = fields[1], fields[3]
            address, local_port = local.rsplit(":", 1)
            if state == LISTEN_STATE and int(local_port, 16) == port:
                addresses.add(prefix + address)
    return addresses


@pytest.fixture
def port_is_listening() -> Callable[[int], bool]:
    """127.0.0.1 のポートへ接続できるかを返す関数。"""
    return is_listening


@pytest.fixture
def addresses_listening() -> Callable[[int], set[str]]:
    """ポートで待ち受けているソケットのアドレスを返す関数。"""
    return listening_addresses


@pytest.fixture
def free_port() -> Callable[[], int]:
    """空いているポートを 1 つ返す関数。"""

    def _free() -> int:
        """ポート 0 で待ち受けて、割り当てられたポートを返す（すぐ閉じる）。"""
        with socket.create_server((HOST, 0)) as probe:
            return int(probe.getsockname()[1])

    return _free


# 辿る時間の上限を 0 秒に差し替えてサーバーを起動するコード（`python -m rule_inject.server` は上限を差し替えられない）
LIMITED_SERVER_CODE = (
    "import os\n"
    "from rule_inject.server.app import build_server\n"
    "server = build_server(os.environ, scan_time_limit=0)\n"
    f"server.run('streamable-http', host='{HOST}', port=int(os.environ['RULE_INJECT_PORT']))\n"
)


def _spawn(
    env: Mapping[str, str], stderr_path: Path, *, limited: bool = False
) -> subprocess.Popen[bytes]:
    """`python -m rule_inject.server` を子プロセスとして起動する（標準エラーはファイルへ書く）。limited なら辿る時間の上限を 0 秒にして起動する。"""
    command = (
        [sys.executable, "-c", LIMITED_SERVER_CODE]
        if limited
        else [sys.executable, "-m", "rule_inject.server"]
    )
    with stderr_path.open("wb") as stderr_file:
        return subprocess.Popen(
            command,
            env=dict(env),
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )


def _wait_ready(server: RunningServer) -> None:
    """サーバーが待ち受けるまで待つ。先に終わったか時間を超えたときは失敗にする。"""
    deadline = time.monotonic() + START_TIMEOUT_SEC
    while not is_listening(server.port):
        if server.process.poll() is not None or time.monotonic() > deadline:
            pytest.fail(f"サーバーが待ち受けなかった: {server.stderr_text()}")
        time.sleep(POLL_INTERVAL_SEC)


def _stop(server: RunningServer) -> None:
    """動いているサーバーを SIGTERM で止める。止まらなければ強制終了する。"""
    if server.process.poll() is not None:
        return
    server.process.send_signal(signal.SIGTERM)
    try:
        server.process.wait(timeout=STOP_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        server.process.kill()
        server.process.wait()


def _server_env(config: Path, state_home: Path, config_home: Path) -> dict[str, str]:
    """このプラグインの環境変数を外し、設定ファイルと状態・設定フォルダだけを指した環境変数を作る。"""
    env = {name: value for name, value in os.environ.items() if not name.startswith("RULE_INJECT_")}
    env["RULE_INJECT_CONFIG"] = str(config)
    env["XDG_CONFIG_HOME"] = str(config_home)
    env["XDG_STATE_HOME"] = str(state_home)
    return env


@pytest.fixture
def start_server(
    tmp_path: Path,
    config_path: Path,
) -> Iterator[Callable[..., RunningServer]]:
    """設定ファイルを書き、サーバーを子プロセスとして起動する factory。終わったら止める。"""
    started: list[RunningServer] = []

    def _start(
        config_text: str,
        *,
        port: int,
        extra_env: Mapping[str, str] | None = None,
        wait_ready: bool = True,
    ) -> RunningServer:
        """設定ファイルを書いて起動する。wait_ready なら待ち受けるまで待つ。"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_text, encoding="utf-8")
        env = _server_env(config_path, tmp_path / "xdg_state", tmp_path / "xdg_config")
        env.update(extra_env or {})
        stderr_path = tmp_path / f"server-{len(started)}.stderr"
        process = _spawn(env, stderr_path)
        server = RunningServer(
            port=port, process=process, config_path=config_path, stderr_path=stderr_path
        )
        started.append(server)
        if wait_ready:
            _wait_ready(server)
        return server

    yield _start
    for server in started:
        _stop(server)


def _start_shared(
    tmp_path_factory: pytest.TempPathFactory, name: str, *, limited: bool
) -> RunningServer:
    """テスト全体で共有するサーバーを、空いているポートで起動して待ち受けるまで待つ。"""
    home = tmp_path_factory.mktemp(name)
    config = home / "config" / "settings.yaml"
    config.parent.mkdir()
    with socket.create_server((HOST, 0)) as probe:
        port = int(probe.getsockname()[1])
    config.write_text(f"global:\n  server_port: {port}\n", encoding="utf-8")
    stderr_path = home / "server.stderr"
    env = _server_env(config, home / "xdg_state", home / "xdg_config")
    env["RULE_INJECT_PORT"] = str(port)
    server = RunningServer(
        port=port,
        process=_spawn(env, stderr_path, limited=limited),
        config_path=config,
        stderr_path=stderr_path,
    )
    _wait_ready(server)
    return server


@pytest.fixture(scope="module")
def shared_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[RunningServer]:
    """ツールの結合テストが共有するサーバー。設定ファイルは呼び出しのたびに読み直されるため、テストごとに書き換える。"""
    server = _start_shared(tmp_path_factory, "shared_server", limited=False)
    yield server
    _stop(server)


@pytest.fixture(scope="module")
def limited_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[RunningServer]:
    """辿る時間の上限を 0 秒にして起動した、ツールの結合テストが共有するサーバー（1 回の呼び出しで 1 つのファイルだけを当てる）。"""
    server = _start_shared(tmp_path_factory, "limited_server", limited=True)
    yield server
    _stop(server)


# 偽の dev-docs を立てるコード。`search_docs` が受けた引数を 1 行ずつ記録し、決めた応答の文字列を返す
FAKE_DEV_DOCS_CODE = (
    "import json, os\n"
    "from mcp.server.mcpserver import MCPServer\n"
    "server = MCPServer('dev-docs')\n"
    "@server.tool()\n"
    "def search_docs(\n"
    "    source: str = '', group_by: str = '', format: str = 'markdown', cwd: str = ''\n"
    ") -> str:\n"
    "    arguments = {'source': source, 'group_by': group_by, 'format': format, 'cwd': cwd}\n"
    "    with open(os.environ['FAKE_CALLS'], 'a', encoding='utf-8') as calls:\n"
    "        calls.write(json.dumps(arguments) + '\\n')\n"
    "    with open(os.environ['FAKE_RESPONSE'], encoding='utf-8') as response:\n"
    "        return response.read()\n"
    f"server.run('streamable-http', host='{HOST}', port=int(os.environ['FAKE_PORT']))\n"
)


@dataclass
class FakeDevDocs:
    """起動した偽の dev-docs の接続先と、受けた `search_docs` の引数の記録。"""

    url: str
    calls_path: Path

    def calls(self) -> list[dict[str, str]]:
        """受けた `search_docs` の引数を、呼ばれた順に返す。"""
        if not self.calls_path.exists():
            return []
        lines = self.calls_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]


@pytest.fixture
def start_fake_dev_docs(
    tmp_path: Path, free_port: Callable[[], int]
) -> Iterator[Callable[[Mapping[str, Any]], FakeDevDocs]]:
    """`search_docs` が決めた応答を返す偽の dev-docs を子プロセスとして立てる factory。終わったら止める。"""
    processes: list[subprocess.Popen[bytes]] = []

    def _start(response: Mapping[str, Any]) -> FakeDevDocs:
        """response の JSON を返す偽の dev-docs を空いているポートで立て、待ち受けるまで待つ。"""
        directory = tmp_path / "fake_dev_docs"
        directory.mkdir(exist_ok=True)
        response_path = directory / "response.json"
        response_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        calls_path = directory / "calls.jsonl"
        port = free_port()
        env = dict(os.environ)
        env.update(
            FAKE_PORT=str(port), FAKE_RESPONSE=str(response_path), FAKE_CALLS=str(calls_path)
        )
        process = subprocess.Popen(
            [sys.executable, "-c", FAKE_DEV_DOCS_CODE],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append(process)
        deadline = time.monotonic() + START_TIMEOUT_SEC
        while not is_listening(port):
            if process.poll() is not None or time.monotonic() > deadline:
                pytest.fail("偽の dev-docs が待ち受けなかった")
            time.sleep(POLL_INTERVAL_SEC)
        return FakeDevDocs(url=f"http://{HOST}:{port}/mcp", calls_path=calls_path)

    yield _start
    for process in processes:
        process.terminate()
        try:
            process.wait(timeout=STOP_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """ツールに渡すプロジェクトの直下。"""
    path = tmp_path / "workspace"
    path.mkdir()
    return path


@pytest.fixture
def config_text() -> Callable[..., str]:
    """`global.server_port` と、`global.indexes`・`projects` を持つ設定ファイルの文字列を返す factory。"""

    def _text(
        port: int,
        *,
        global_indexes: Sequence[Path] = (),
        match: Path | None = None,
        project_indexes: Sequence[Path] = (),
        dev_docs_url: str | None = None,
    ) -> str:
        """port のポートと、渡した索引・プロジェクトの要素・dev-docs の接続先を書いた設定ファイルの文字列を作る。"""
        lines = ["global:", f"  server_port: {port}"]
        if dev_docs_url is not None:
            lines.append(f"  dev_docs_url: {dev_docs_url}")
        if global_indexes:
            lines.append("  indexes:")
            lines.extend(f"    - {index}" for index in global_indexes)
        if match is not None:
            lines.extend(["projects:", f"  - match: {match}", "    indexes:"])
            lines.extend(f"      - {index}" for index in project_indexes)
        return "\n".join(lines) + "\n"

    return _text


@pytest.fixture
def running_server(
    shared_server: RunningServer,
    config_text: Callable[..., str],
    project_dir: Path,
) -> Callable[..., RunningServer]:
    """プロジェクトの直下に当たる要素に索引を並べた設定ファイルを書き、共有のサーバーを返す factory。"""

    def _use(
        *project_indexes: Path,
        global_indexes: Sequence[Path] = (),
        dev_docs_url: str | None = None,
    ) -> RunningServer:
        """project_indexes を `projects` の要素の `indexes` に、global_indexes を `global.indexes` に、dev_docs_url を `global.dev_docs_url` に置く。"""
        text = config_text(
            shared_server.port,
            global_indexes=global_indexes,
            match=project_dir if project_indexes else None,
            project_indexes=project_indexes,
            dev_docs_url=dev_docs_url,
        )
        shared_server.config_path.write_text(text, encoding="utf-8")
        return shared_server

    return _use


@pytest.fixture
def running_limited_server(
    limited_server: RunningServer,
    config_text: Callable[..., str],
    project_dir: Path,
) -> Callable[..., RunningServer]:
    """`running_server` と同じ設定ファイルを書き、辿る時間の上限を 0 秒にしたサーバーを返す factory。"""

    def _use(*project_indexes: Path, global_indexes: Sequence[Path] = ()) -> RunningServer:
        """project_indexes を `projects` の要素の `indexes` に、global_indexes を `global.indexes` に置く。"""
        text = config_text(
            limited_server.port,
            global_indexes=global_indexes,
            match=project_dir if project_indexes else None,
            project_indexes=project_indexes,
        )
        limited_server.config_path.write_text(text, encoding="utf-8")
        return limited_server

    return _use


@pytest.fixture
def record_server(shared_server: RunningServer, state_dir: Path) -> RunningServer:
    """`global.state_dir` でテストの記録フォルダを指した設定ファイルを書き、共有のサーバーを返す。"""
    text = f"global:\n  server_port: {shared_server.port}\n  state_dir: {state_dir}\n"
    shared_server.config_path.write_text(text, encoding="utf-8")
    return shared_server


@pytest.fixture
def write_history_rows(state_dir: Path, session_id: str) -> Callable[..., Path]:
    """既読の履歴ファイルを、行を 1 行ずつ書いて置く factory。dict は JSON にし、文字列はそのまま書く。"""

    def _write(rows: Sequence[Mapping[str, Any] | str], name: str | None = None) -> Path:
        """rows を 1 行ずつ、name（無ければこのセッション）の既読の履歴ファイルに書く。"""
        path = state_dir / f"{name or session_id}.history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [row if isinstance(row, str) else json.dumps(row) for row in rows]
        path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def make_project_files(project_dir: Path) -> Callable[..., None]:
    """プロジェクトの直下の下に、空のファイルをフォルダごと置く factory。"""

    def _make(*names: str) -> None:
        """names の相対パスのファイルを置く。"""
        for name in names:
            path = project_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

    return _make


@pytest.fixture
def hashed() -> Callable[[Path], str]:
    """ルールのファイルの中身の SHA-256 を、既読の記録の書式（`sha256:{16 進数}`）で返す関数。"""

    def _hash(path: Path) -> str:
        """path の中身のハッシュを返す。"""
        return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"

    return _hash


@pytest.fixture
def invalid_config(shared_server: RunningServer) -> Callable[[], str]:
    """共有のサーバーの設定ファイルを、`global` に知らないキーを持つ内容へ書き換える関数。設定ファイルの場所を返す。"""

    def _break() -> str:
        """設定ファイルを読めない内容にして、その場所を返す。"""
        shared_server.config_path.write_text("global:\n  foo: 1\n", encoding="utf-8")
        return str(shared_server.config_path)

    return _break


@pytest.fixture
def list_revs(project_dir: Path) -> Callable[[RunningServer], list[str]]:
    """`list_rules` が返す効いているエントリのバージョンを、位置の順に返す関数。"""

    def _revs(server: RunningServer) -> list[str]:
        """`list_rules` を呼び、`entries[].rev` を並べる。"""
        result = server.call("list_rules", project_dir=str(project_dir), format="json")
        return [entry["rev"] for entry in result.structured_content["entries"]]

    return _revs


@pytest.fixture
def text_of() -> Callable[[CallToolResult], str]:
    """ツールの結果の text を返す関数。"""

    def _text(result: CallToolResult) -> str:
        """結果の content の text をつなげる。"""
        return "\n".join(getattr(content, "text", "") for content in result.content)

    return _text
