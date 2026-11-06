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
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult

HOST = "127.0.0.1"
# 1 回の起動で、標準エラーに待ち受けの開始の行が出るまでを待つ上限（導き方はテスト実行方法の結合テスト（バック）の補足「起動を待つ上限」）
START_TIMEOUT_SEC = 51
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
    "from pathlib import Path\n"
    "import rule_inject.server as package\n"
    "from rule_inject.server.app import build_server\n"
    "from rule_inject.server.clone import find_clone\n"
    "from rule_inject.server.control import ServerControl\n"
    "port = int(os.environ['RULE_INJECT_PORT'])\n"
    "server = build_server(\n"
    "    os.environ,\n"
    "    control=ServerControl(port=port),\n"
    "    clone=find_clone(Path(package.__file__).parent),\n"
    "    scan_time_limit=0,\n"
    ")\n"
    f"server.run('streamable-http', host='{HOST}', port=port)\n"
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
        make_config: Callable[[], str], port: int, attempt: int
    ) -> tuple[subprocess.Popen[bytes], Path]:
        """設定ファイルを書き、port を `RULE_INJECT_PORT` に渡して起動する。"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(make_config(), encoding="utf-8")
        env = _server_env(config_path, tmp_path / "xdg_state", tmp_path / "xdg_config")
        env["RULE_INJECT_PORT"] = str(port)
        stderr_path = tmp_path / f"server-{len(started)}-{attempt}.stderr"
        return _spawn(env, stderr_path), stderr_path

    def _start(
        make_config: Callable[[], str],
        *,
        port: int | None = None,
        wait_ready: bool = True,
    ) -> RunningServer:
        """make_config の設定ファイルと空いているポート（port があればそのポート）で起動する。

        wait_ready なら待ち受けるまで待ち、待ち受けに失敗したら別のポートで起動し直す。
        wait_ready でなければ 1 回だけ起動して待たない（起動に失敗する確かめに使う）。
        """
        if wait_ready:
            used, process, stderr_path = _launch(
                lambda free, attempt: _spawn_at(make_config, free, attempt)
            )
        else:
            used = port if port is not None else _free_port()
            process, stderr_path = _spawn_at(make_config, used, 0)
        server = RunningServer(
            port=used, process=process, config_path=config_path, stderr_path=stderr_path
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
        """起動し直したポートを `RULE_INJECT_PORT` に渡して起動する。"""
        config.write_text("", encoding="utf-8")
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


# 偽の dev-docs を立てるコード。`search_docs` が受けた引数を 1 行ずつ記録し、`FAKE_DELAY` 秒待ってから決めた応答の文字列を返す
FAKE_DEV_DOCS_CODE = (
    "import json, os, time\n"
    "from mcp.server.mcpserver import MCPServer\n"
    "server = MCPServer('dev-docs')\n"
    "@server.tool()\n"
    "def search_docs(\n"
    "    source: str = '', group_by: str = '', format: str = 'markdown', cwd: str = ''\n"
    ") -> str:\n"
    "    arguments = {'source': source, 'group_by': group_by, 'format': format, 'cwd': cwd}\n"
    "    with open(os.environ['FAKE_CALLS'], 'a', encoding='utf-8') as calls:\n"
    "        calls.write(json.dumps(arguments) + '\\n')\n"
    "    time.sleep(float(os.environ.get('FAKE_DELAY', '0')))\n"
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
def start_fake_dev_docs(tmp_path: Path) -> Iterator[Callable[..., FakeDevDocs]]:
    """`search_docs` が決めた応答を返す偽の dev-docs を子プロセスとして立てる factory。終わったら止める。"""
    processes: list[subprocess.Popen[bytes]] = []

    def _start(response: Mapping[str, Any], *, delay: float = 0) -> FakeDevDocs:
        """response の JSON を delay 秒待ってから返す偽の dev-docs を空いているポートで立て、待ち受けるまで待つ。"""
        directory = tmp_path / "fake_dev_docs"
        directory.mkdir(exist_ok=True)
        response_path = directory / "response.json"
        response_path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
        calls_path = directory / "calls.jsonl"

        def _spawn_at(port: int, attempt: int) -> tuple[subprocess.Popen[bytes], Path]:
            """port で偽の dev-docs を起動する（標準エラーは起動の確かめのためファイルへ書く）。"""
            env = dict(os.environ)
            env.update(
                FAKE_PORT=str(port),
                FAKE_RESPONSE=str(response_path),
                FAKE_CALLS=str(calls_path),
                FAKE_DELAY=str(delay),
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
    """`global.indexes`・`global.dev_docs_url`・`projects` を持つ設定ファイルの文字列を返す factory。"""

    def _text(
        *,
        global_indexes: Sequence[Path] = (),
        match: Path | None = None,
        project_indexes: Sequence[Path] = (),
        dev_docs_url: str | None = None,
    ) -> str:
        """渡した索引・プロジェクトの要素・dev-docs の接続先を書いた設定ファイルの文字列を作る。"""
        lines: list[str] = []
        # global のキーがあるときだけ見出しを置く
        if dev_docs_url is not None or global_indexes:
            lines.append("global:")
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
    text = f"global:\n  state_dir: {state_dir}\n"
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


# 再起動の後に接続し直せるようになるまで、状態の確認を呼び直す上限（秒）。起動を待つ上限と同じ
RESTART_WAIT_SEC = START_TIMEOUT_SEC


def call_quietly(server: RunningServer, name: str, **arguments: Any) -> CallToolResult | None:
    """ツールを呼び、接続できない・接続が切れたときは None を返す。"""
    # 接続の失敗は SDK が ExceptionGroup に包んで送出する（mcp の外部ライブラリの設計書）
    try:
        return server.call(name, **arguments)
    except (ExceptionGroup, OSError, TimeoutError, MCPError):
        return None


@pytest.fixture
def wait_restarted() -> Callable[[RunningServer, str], dict[str, Any]]:
    """`get_server_status` の `started_at` が before より新しくなるまで呼び直し、その応答を返す関数。"""

    def _wait(server: RunningServer, before: str) -> dict[str, Any]:
        """再起動の後に接続し直せるまで待つ。上限を過ぎたら失敗にする。"""
        deadline = time.monotonic() + RESTART_WAIT_SEC
        while time.monotonic() < deadline:
            result = call_quietly(server, "get_server_status")
            # 接続でき、起動した時刻が新しくなった: 起動し直した
            if result is not None and result.structured_content["started_at"] > before:
                return dict(result.structured_content)
            time.sleep(POLL_INTERVAL_SEC)
        pytest.fail(f"{RESTART_WAIT_SEC} 秒で起動し直さなかった: {server.stderr_text()}")

    return _wait


# テストの commit の作者（利用者の git の設定を読まない）
GIT_IDENTITY = ("-c", "user.name=test", "-c", "user.email=test@example.com")


def git(cwd: Path, *args: str) -> str:
    """cwd で git を実行し、標準出力を返す。"""
    completed = subprocess.run(
        ["git", *GIT_IDENTITY, *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


@dataclass
class CloneRepos:
    """作業ブランチから作った上流の bare リポジトリと、サーバーを動かすクローンと、上流へ commit を積む作業用のクローン。"""

    upstream: Path
    clone: Path
    pusher: Path

    def push(self, name: str, text: str = "x\n") -> str:
        """作業用のクローンにファイルを 1 つ足して commit し、上流へ push して commit を返す。"""
        (self.pusher / name).write_text(text, encoding="utf-8")
        git(self.pusher, "add", name)
        git(self.pusher, "commit", "-m", name)
        git(self.pusher, "push", "-q", "origin", "HEAD")
        return git(self.pusher, "rev-parse", "HEAD")

    def head(self) -> str:
        """サーバーを動かすクローンの HEAD を返す。"""
        return git(self.clone, "rev-parse", "HEAD")


@pytest.fixture
def clone_repos(tmp_path: Path) -> CloneRepos:
    """作業ブランチの HEAD から、上流の bare リポジトリと 2 つのクローンを一時フォルダに作る。"""
    source = Path(git(Path(__file__).parent, "rev-parse", "--show-toplevel"))
    upstream = tmp_path / "upstream.git"
    subprocess.run(
        ["git", "clone", "-q", "--bare", "--no-hardlinks", str(source), str(upstream)], check=True
    )
    branch = git(source, "rev-parse", "--abbrev-ref", "HEAD")
    clone = tmp_path / "clone"
    pusher = tmp_path / "pusher"
    for target in (clone, pusher):
        subprocess.run(
            ["git", "clone", "-q", "--branch", branch, str(upstream), str(target)], check=True
        )
    return CloneRepos(upstream=upstream, clone=clone, pusher=pusher)


# クローンのコードを読む起動の入口。FAIL_UV が立っていれば、uv sync だけ終了コード 1 を返す run_command で組み立てる
CLONE_SERVER_CODE = (
    "import os, sys\n"
    "from pathlib import Path\n"
    "import uvicorn\n"
    "import rule_inject.server as package\n"
    "from rule_inject.server import __main__ as entry\n"
    "from rule_inject.server.app import build_server\n"
    "from rule_inject.server.clone import CommandResult, find_clone, run_command\n"
    "from rule_inject.server.control import GRACEFUL_SHUTDOWN_TIMEOUT, ServerControl\n"
    "def failing_uv(args, *, cwd, timeout, env=None):\n"
    "    if 'sync' in args:\n"
    "        return CommandResult(returncode=1, stdout='', stderr='error: uv sync に失敗した')\n"
    "    return run_command(args, cwd=cwd, timeout=timeout, env=env)\n"
    "if not os.environ.get('FAIL_UV'):\n"
    "    entry.main()\n"
    "    sys.exit(0)\n"
    "port = int(os.environ['RULE_INJECT_PORT'])\n"
    "control = ServerControl(port=port)\n"
    "clone = find_clone(Path(package.__file__).parent)\n"
    "app = build_server(os.environ, control=control, clone=clone, run_command=failing_uv)\n"
    f"server = uvicorn.Server(uvicorn.Config(app.streamable_http_app(host='{HOST}'), "
    f"host='{HOST}', port=port, timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT))\n"
    "control.attach(server)\n"
    "server.run()\n"
)


@pytest.fixture
def start_clone_server(
    tmp_path: Path, clone_repos: CloneRepos
) -> Iterator[Callable[..., RunningServer]]:
    """クローンの `src` を `PYTHONPATH` に置いてサーバーを子プロセスとして起動する factory。終わったら止める。"""
    started: list[RunningServer] = []
    config = tmp_path / "clone_config" / "settings.yaml"
    config.parent.mkdir()
    config.write_text("", encoding="utf-8")

    def _start(*, fail_uv: bool = False) -> RunningServer:
        """クローンのコードで起動し、待ち受けるまで待つ。fail_uv なら uv sync だけ失敗させる。"""

        def _spawn_at(port: int, attempt: int) -> tuple[subprocess.Popen[bytes], Path]:
            """port を `RULE_INJECT_PORT` に渡して起動する。"""
            env = _server_env(config, tmp_path / "xdg_state", tmp_path / "xdg_config")
            env["RULE_INJECT_PORT"] = str(port)
            env["PYTHONPATH"] = str(clone_repos.clone / "src")
            if fail_uv:
                env["FAIL_UV"] = "1"
            stderr_path = tmp_path / f"clone-server-{len(started)}-{attempt}.stderr"
            with stderr_path.open("wb") as stderr_file:
                process = subprocess.Popen(
                    [sys.executable, "-c", CLONE_SERVER_CODE],
                    env=env,
                    cwd=tmp_path,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_file,
                )
            return process, stderr_path

        port, process, stderr_path = _launch(_spawn_at)
        server = RunningServer(
            port=port, process=process, config_path=config, stderr_path=stderr_path
        )
        started.append(server)
        return server

    yield _start
    for server in started:
        _stop(server)
