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
# 待ち受けに失敗して子プロセスが終わったとき、別の空いているポートで起動し直す回数の上限（導き方はテスト実行方法の結合テスト（バック）の補足「起動し直す回数」）
START_ATTEMPTS = 5
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
def addresses_listening() -> Callable[[int], set[str]]:
    """ポートで待ち受けているソケットのアドレスを返す関数。"""
    return listening_addresses


def _free_port() -> int:
    """ポート 0 で待ち受けて、割り当てられたポートを返す（すぐ閉じる）。

    閉じてから子プロセスが待ち受けるまでの間に他のプロセスが同じポートを取ることがあるため、
    この番号で起動する側は `_launch` で起動を確かめ、失敗したら別の番号で起動し直す。
    """
    with socket.create_server((HOST, 0)) as probe:
        return int(probe.getsockname()[1])


def ready_line(port: int) -> str:
    """uvicorn が待ち受けを始めたときに標準エラーへ書く行（`port` で待ち受けたときだけ出る）。"""
    return f"Uvicorn running on http://{HOST}:{port}"


def _wait_ready(process: subprocess.Popen[bytes], stderr_path: Path, port: int) -> bool:
    """標準エラーに `port` の待ち受けの開始の行が出るまで待つ。

    先に子プロセスが終わったときは、待ち受けに失敗したとして False を返す。
    時間を超えたときは子プロセスを止めて失敗にする。
    """
    deadline = time.monotonic() + START_TIMEOUT_SEC
    while True:
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        # 行が出ている: このポートで待ち受けている（他のプロセスの待ち受けでは出ない）
        if ready_line(port) in stderr:
            return True
        # 行が出ないまま終わった: 待ち受けに失敗した（ポートを他のプロセスに取られた等）
        if process.poll() is not None:
            return False
        # 終わらず行も出ない: 時間の上限まで待ち、超えたら止めて失敗にする
        if time.monotonic() > deadline:
            process.kill()
            process.wait()
            pytest.fail(f"{START_TIMEOUT_SEC} 秒で待ち受けなかった: {stderr}")
        time.sleep(POLL_INTERVAL_SEC)


def _launch(
    spawn: Callable[[int, int], tuple[subprocess.Popen[bytes], Path]],
) -> tuple[int, subprocess.Popen[bytes], Path]:
    """空いているポートで子プロセスを起動して待ち受けるまで待ち、失敗したら別のポートで起動し直す。

    spawn は (ポート, 何回目か) を受けて起動し、子プロセスと標準エラーのファイルを返す。
    待ち受けたポート・子プロセス・標準エラーのファイルを返す。`START_ATTEMPTS` 回とも失敗したら失敗にする。
    """
    stderr = ""
    for attempt in range(START_ATTEMPTS):
        port = _free_port()
        process, stderr_path = spawn(port, attempt)
        if _wait_ready(process, stderr_path, port):
            return port, process, stderr_path
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    pytest.fail(f"{START_ATTEMPTS} 回起動し直しても待ち受けなかった: {stderr}")


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

    def _spawn_at(
        make_config: Callable[[int], str], port: int, attempt: int, *, port_env: bool
    ) -> tuple[subprocess.Popen[bytes], Path]:
        """port を渡して設定ファイルを書き、起動する。port_env なら port を `RULE_INJECT_PORT` にも渡す。"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(make_config(port), encoding="utf-8")
        env = _server_env(config_path, tmp_path / "xdg_state", tmp_path / "xdg_config")
        if port_env:
            env["RULE_INJECT_PORT"] = str(port)
        stderr_path = tmp_path / f"server-{len(started)}-{attempt}.stderr"
        return _spawn(env, stderr_path), stderr_path

    def _start(
        make_config: Callable[[int], str],
        *,
        port_env: bool = False,
        wait_ready: bool = True,
    ) -> RunningServer:
        """空いているポートを make_config に渡して書いた設定ファイルで起動する。

        wait_ready なら待ち受けるまで待ち、待ち受けに失敗したら別のポートで起動し直す。
        wait_ready でなければ 1 回だけ起動して待たない（起動に失敗する確かめに使う）。
        """
        if wait_ready:
            port, process, stderr_path = _launch(
                lambda port, attempt: _spawn_at(make_config, port, attempt, port_env=port_env)
            )
        else:
            port = _free_port()
            process, stderr_path = _spawn_at(make_config, port, 0, port_env=port_env)
        server = RunningServer(
            port=port, process=process, config_path=config_path, stderr_path=stderr_path
        )
        started.append(server)
        return server

    yield _start
    for server in started:
        _stop(server)


def _start_shared(
    tmp_path_factory: pytest.TempPathFactory, name: str, *, limited: bool
) -> RunningServer:
    """テスト全体で共有するサーバーを、空いているポートで起動して待ち受けるまで待つ（失敗したら別のポートで起動し直す）。"""
    home = tmp_path_factory.mktemp(name)
    config = home / "config" / "settings.yaml"
    config.parent.mkdir()
    env = _server_env(config, home / "xdg_state", home / "xdg_config")

    def _spawn_at(port: int, attempt: int) -> tuple[subprocess.Popen[bytes], Path]:
        """起動し直したポートを設定ファイルの `global.server_port` と `RULE_INJECT_PORT` に揃えて起動する。"""
        config.write_text(f"global:\n  server_port: {port}\n", encoding="utf-8")
        stderr_path = home / f"server-{attempt}.stderr"
        return _spawn(
            {**env, "RULE_INJECT_PORT": str(port)}, stderr_path, limited=limited
        ), stderr_path

    port, process, stderr_path = _launch(_spawn_at)
    return RunningServer(port=port, process=process, config_path=config, stderr_path=stderr_path)


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
def start_fake_dev_docs(tmp_path: Path) -> Iterator[Callable[[Mapping[str, Any]], FakeDevDocs]]:
    """`search_docs` が決めた応答を返す偽の dev-docs を子プロセスとして立てる factory。終わったら止める。"""
    processes: list[subprocess.Popen[bytes]] = []

    def _start(response: Mapping[str, Any]) -> FakeDevDocs:
        """response の JSON を返す偽の dev-docs を空いているポートで立て、待ち受けるまで待つ。"""
        directory = tmp_path / "fake_dev_docs"
        directory.mkdir(exist_ok=True)
        response_path = directory / "response.json"
        response_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        calls_path = directory / "calls.jsonl"

        def _spawn_at(port: int, attempt: int) -> tuple[subprocess.Popen[bytes], Path]:
            """port で偽の dev-docs を起動する（標準エラーは起動の確かめのためファイルへ書く）。"""
            env = dict(os.environ)
            env.update(
                FAKE_PORT=str(port), FAKE_RESPONSE=str(response_path), FAKE_CALLS=str(calls_path)
            )
            stderr_path = directory / f"fake-{len(processes)}-{attempt}.stderr"
            with stderr_path.open("wb") as stderr_file:
                process = subprocess.Popen(
                    [sys.executable, "-c", FAKE_DEV_DOCS_CODE],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_file,
                )
            return process, stderr_path

        port, process, _ = _launch(_spawn_at)
        processes.append(process)
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
