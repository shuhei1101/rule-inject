"""ルール本文の取得（MCP のツール read_rules）の結合テスト。"""

from __future__ import annotations

import asyncio
import io
import json
import urllib.error
from collections.abc import Callable, Mapping
from email.message import Message
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from mcp.client import Client

from rule_inject.server.app import build_server

RULE_URL = "https://example.com/rules/web.md"
NOT_FOUND_URL = "https://example.com/rules/not-found.md"
SLOW_URL = "https://example.com/rules/slow.md"
MAX_RESULT_CHARS = 40000


@pytest.fixture
def server_env(
    base_env: dict[str, str], make_index: Callable[..., Path], index_text: Callable[..., str]
) -> Callable[..., Mapping[str, str]]:
    """エントリを並べた索引を書き、それをプロジェクト用の索引に指す環境変数を返す factory。"""

    def _env(*entries: dict[str, Any]) -> Mapping[str, str]:
        """entries の索引を置き、base_env に索引の環境変数を足す。"""
        index = make_index(index_text(*entries))
        return {**base_env, "RULE_INJECT_INDEXES_PROJECT": str(index)}

    return _env


@pytest.fixture
def call_read_rules() -> Callable[..., Any]:
    """MCP のクライアントでサーバーの read_rules を呼び、応答を返す factory。"""

    async def _call(env: Mapping[str, str], arguments: dict[str, Any]) -> Any:
        """サーバーをメモリ上でつないで read_rules を呼ぶ。"""
        async with Client(build_server(env)) as client:
            return await client.call_tool("read_rules", arguments)

    def _run(env: Mapping[str, str], arguments: dict[str, Any]) -> Any:
        """呼び出しを同期で待つ。"""
        return asyncio.run(_call(env, arguments))

    return _run


def _ok_response(body: str) -> MagicMock:
    """200 と本文を返す urlopen の応答。"""
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.getcode.return_value = 200
    response.read.return_value = body.encode("utf-8")
    return response


def _payload(result: Any) -> dict[str, Any]:
    """read_rules の応答（JSON の文字列）を dict にする。"""
    return json.loads(result.content[0].text)


def test_normal(
    tmp_path: Path,
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    rule_file: Callable[..., Path],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """ローカルの場所の本文を返して既読にする（正常系）。"""
    # 準備
    rule = rule_file("python.md", "# Python の規約\n")
    env = server_env({"rule": str(rule)})
    # 実行
    result = call_read_rules(env, {"locations": [str(rule)], "session_id": session_id})
    # 検証
    assert _payload(result)["pages"] == [{"location": str(rule), "body": "# Python の規約\n"}]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "read_rules"
    assert history[0]["tool"] == "mcp__plugin_rule-inject_rule-inject__read_rules"
    assert history[0]["location"] == str(rule)
    assert "history_failures" not in _payload(result)


def test_normal_when_by_target_path(
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    rule_file: Callable[..., Path],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """対象のパスに当たるルールだけの本文を返す（正常系）。"""
    # 準備
    py_rule = rule_file("python.md", "# Python の規約\n")
    ts_rule = rule_file("typescript.md", "# TypeScript の規約\n")
    env = server_env(
        {"rule": str(py_rule), "paths": ["**/*.py"]},
        {"rule": str(ts_rule), "paths": ["**/*.ts"]},
    )
    # 実行
    result = call_read_rules(env, {"paths": ["/p/src/app.py"], "session_id": session_id})
    # 検証
    assert _payload(result)["pages"] == [{"location": str(py_rule), "body": "# Python の規約\n"}]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(py_rule)]


def test_normal_when_url(
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """URL の場所の本文を HTTPS で取得して返す（正常系）。"""
    # 準備
    env = server_env({"rule": RULE_URL})
    # 実行
    with patch("urllib.request.urlopen", return_value=_ok_response("# Web の規約\n")) as urlopen:
        result = call_read_rules(env, {"locations": [RULE_URL], "session_id": session_id})
    # 検証
    assert _payload(result)["pages"] == [{"location": RULE_URL, "body": "# Web の規約\n"}]
    assert read_lines(state_dir / f"{session_id}.txt") == [RULE_URL]
    assert urlopen.call_args.kwargs["timeout"] == 1.0


def test_normal_when_over_limit(
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    rule_file: Callable[..., Path],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """収まらない本文を deferred に回し、既読にしない（正常系）。"""
    # 準備
    first = rule_file("a.md", "a" * 16000)
    second = rule_file("b.md", "b" * 16000)
    third = rule_file("c.md", "c" * 16000)
    env = server_env({"rule": str(first)}, {"rule": str(second)}, {"rule": str(third)})
    locations = [str(first), str(second), str(third)]

    async def _list_tools() -> Any:
        """サーバーの tools/list を返す。"""
        async with Client(build_server(env)) as client:
            return (await client.list_tools()).tools

    # 実行
    result = call_read_rules(env, {"locations": locations, "session_id": session_id})
    tools = asyncio.run(_list_tools())
    # 検証
    assert len(result.content[0].text) <= MAX_RESULT_CHARS
    assert _payload(result)["deferred"] == [str(third)]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(first), str(second)]
    history = read_history()
    assert len(history) == 2
    assert history[0]["location"] == str(first)
    assert history[1]["location"] == str(second)
    assert tools[0].meta["anthropic/maxResultSizeChars"] == MAX_RESULT_CHARS


def test_error_when_location_unreadable(
    tmp_path: Path,
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    state_dir: Path,
    session_id: str,
) -> None:
    """実在しない場所と、取得に失敗した URL を failures に載せ、再試行も既読もしない（異常系）。"""
    # 準備
    missing = tmp_path / "rules" / "missing.md"
    env = server_env({"rule": str(missing)}, {"rule": NOT_FOUND_URL}, {"rule": SLOW_URL})
    errors = {
        NOT_FOUND_URL: urllib.error.HTTPError(
            NOT_FOUND_URL, 404, "Not Found", Message(), io.BytesIO()
        ),
        SLOW_URL: TimeoutError("timed out"),
    }

    def _urlopen(url: str, timeout: float) -> Any:
        """URL ごとに決めた失敗を送出する。"""
        raise errors[url]

    # 実行
    with patch("urllib.request.urlopen", side_effect=_urlopen) as urlopen:
        result = call_read_rules(
            env,
            {"locations": [str(missing), NOT_FOUND_URL, SLOW_URL], "session_id": session_id},
        )
    # 検証
    failures = _payload(result)["failures"]
    assert len(failures) == 3
    assert failures[1]["reason"] == "HTTP 404"
    assert "待ち時間" in failures[2]["reason"]
    assert urlopen.call_count == 2
    assert not (state_dir / f"{session_id}.txt").exists()


@pytest.mark.parametrize(
    ("arguments", "missing_name"),
    [
        pytest.param({"locations": ["/r/a.md"]}, "session_id", id="no_session_id"),
        pytest.param({"session_id": "s1"}, "locations", id="no_target"),
    ],
)
def test_error_when_arguments_missing(
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    state_dir: Path,
    arguments: dict[str, Any],
    missing_name: str,
) -> None:
    """session_id が無い呼び出しと、引く対象が無い呼び出しをエラーにする（異常系）。"""
    # 準備
    env = server_env({"rule": "/r/a.md"})
    # 実行
    result = call_read_rules(env, arguments)
    # 検証
    assert result.is_error is True
    assert missing_name in result.content[0].text
    assert list(state_dir.glob("*.txt")) == []


def test_error_when_location_not_in_index(
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    rule_file: Callable[..., Path],
    state_dir: Path,
    session_id: str,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """索引に無い絶対パスと URL を読まずに failures に載せる（異常系）。"""
    # 準備
    listed = rule_file("listed.md")
    unlisted = unwritable(rule_file("unlisted.md"), 0o000)
    env = server_env({"rule": str(listed)})
    # 実行
    with patch("urllib.request.urlopen", side_effect=AssertionError("取得しない")) as urlopen:
        result = call_read_rules(
            env, {"locations": [str(unlisted), RULE_URL], "session_id": session_id}
        )
    # 検証
    payload = _payload(result)
    assert payload["pages"] == []
    assert len(payload["failures"]) == 2
    assert "索引に載っていない場所" in payload["failures"][0]["reason"]
    assert "索引に載っていない場所" in payload["failures"][1]["reason"]
    urlopen.assert_not_called()
    assert list(state_dir.glob("*.txt")) == []


def test_error_when_record_unwritable(
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    rule_file: Callable[..., Path],
    state_dir: Path,
    log_folder: Path,
    session_id: str,
    unwritable: Callable[[Path, int], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """記録のフォルダに書けないとき、記録フォルダの場所と理由を載せたエラーにする（異常系）。"""
    # 準備
    rule = rule_file("python.md")
    env = server_env({"rule": str(rule)})
    state_dir.mkdir()
    unwritable(state_dir, 0o555)
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    # 実行
    result = call_read_rules(env, {"locations": [str(rule)], "session_id": session_id})
    # 検証
    assert result.is_error is True
    assert str(state_dir) in result.content[0].text
    assert "PermissionError" in result.content[0].text
    assert '"operation": "write_record"' in capsys.readouterr().err


def test_normal_when_body_has_variables(
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    rule_file: Callable[..., Path],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """設定された名前を展開し、未設定の名前を残して本文の先頭に注釈を足す（正常系）。"""
    # 準備
    body = (
        "# 規約\n"
        "set: !{SET_NAME}\n"
        "empty: [!{EMPTY_NAME}]\n"
        "unset: !{UNSET_NAME} / !{UNSET_NAME}\n"
        "spaced: !{ SET_NAME }\n"
    )
    rule = rule_file("var.md", body)
    env = {**server_env({"rule": str(rule)}), "SET_NAME": "value-1", "EMPTY_NAME": ""}
    # 実行
    result = call_read_rules(env, {"locations": [str(rule)], "session_id": session_id})
    # 検証
    expanded = _payload(result)["pages"][0]["body"]
    assert "set: value-1" in expanded
    assert "!{SET_NAME}" not in expanded
    assert "empty: []" in expanded
    assert "unset: !{UNSET_NAME} / !{UNSET_NAME}" in expanded
    assert "spaced: !{ SET_NAME }" in expanded
    assert expanded.splitlines()[0] == (
        "> 注釈: 次の変数参照は、環境変数が設定されていないため展開していない: UNSET_NAME"
    )
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]


def test_normal_when_history_unwritable(
    server_env: Callable[..., Mapping[str, str]],
    call_read_rules: Callable[..., Any],
    rule_file: Callable[..., Path],
    state_dir: Path,
    log_folder: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    unwritable: Callable[[Path, int], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """既読の履歴に書けないときも本文を返して既読にし、書けなかった場所と理由を応答に載せる（正常系）。"""
    # 準備
    rule = rule_file("python.md", "# Python の規約\n")
    env = server_env({"rule": str(rule)})
    (state_dir / f"{session_id}.history.jsonl").mkdir(parents=True)
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    # 実行
    result = call_read_rules(env, {"locations": [str(rule)], "session_id": session_id})
    # 検証
    payload = _payload(result)
    assert payload["pages"] == [{"location": str(rule), "body": "# Python の規約\n"}]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]
    assert payload["history_failures"][0]["location"] == str(rule)
    assert "IsADirectoryError" in payload["history_failures"][0]["reason"]
    assert '"operation": "write_history"' in capsys.readouterr().err
