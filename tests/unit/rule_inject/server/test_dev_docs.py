"""server/dev_docs.py の単体テスト。"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import pytest
from mcp.types import CallToolResult, TextContent

DEV_DOCS_URL = "http://127.0.0.1:8781/mcp"
PROJECT_DIR = "/p/project"
# 待ち時間の上限（秒）。応答を待ち終えられる値
TIMEOUT = 5.0

OpenSession = Callable[[str], AbstractAsyncContextManager[Any]]


class FakeSession:
    """受けた呼び出しを記録し、決めた結果を返す dev-docs のセッションの偽物。"""

    def __init__(self, result: CallToolResult, delay: float, calls: list[dict[str, Any]]) -> None:
        """返す結果と、返す前に待つ秒数と、呼び出しを記録するリストを持つ。"""
        self._result = result
        self._delay = delay
        self._calls = calls

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        """ツール名と引数を記録し、delay 秒待ってから結果を返す。"""
        self._calls.append({"name": name, "arguments": arguments})
        await asyncio.sleep(self._delay)
        return self._result


@pytest.fixture
def fake_open_session() -> Callable[..., tuple[OpenSession, list[dict[str, Any]]]]:
    """決めた結果を返す偽のセッションを開く関数と、受けた呼び出しの記録を返す factory。"""

    def _make(
        text: str, *, is_error: bool = False, delay: float = 0.0
    ) -> tuple[OpenSession, list[dict[str, Any]]]:
        """text を結果の文字列にする偽のセッションを開く関数を作る。"""
        calls: list[dict[str, Any]] = []
        result = CallToolResult(content=[TextContent(type="text", text=text)], is_error=is_error)

        @asynccontextmanager
        async def open_session(url: str) -> AsyncIterator[FakeSession]:
            """接続先を記録し、偽のセッションを渡す。"""
            calls.append({"url": url})
            yield FakeSession(result, delay, calls)

        return open_session, calls

    return _make


def test_fetch_used_tags(
    fake_open_session: Callable[..., tuple[OpenSession, list[dict[str, Any]]]],
) -> None:
    """groups の値を使われているタグにする（正常系）。"""
    from rule_inject.server.dev_docs import fetch_used_tags

    # 準備
    body = {
        "total_count": 3,
        "groups": [{"value": "Python", "count": 2}, {"value": "mcp", "count": 1}],
    }
    open_session, calls = fake_open_session(json.dumps(body))
    # 実行
    result = asyncio.run(
        fetch_used_tags(DEV_DOCS_URL, PROJECT_DIR, timeout=TIMEOUT, open_session=open_session)
    )
    # 検証
    assert result.tags == ("Python", "mcp")
    assert result.reason is None
    assert calls == [
        {"url": DEV_DOCS_URL},
        {
            "name": "search_docs",
            "arguments": {"source": "*", "group_by": "tags", "format": "json", "cwd": PROJECT_DIR},
        },
    ]


def test_fetch_used_tags_when_no_tag_group(
    fake_open_session: Callable[..., tuple[OpenSession, list[dict[str, Any]]]],
) -> None:
    """タグを持たない文書のグループは使われているタグに含めない（正常系）。"""
    from rule_inject.server.dev_docs import fetch_used_tags

    # 準備
    body = {
        "total_count": 3,
        "groups": [{"value": "python", "count": 2}, {"value": "（なし）", "count": 1}],
    }
    open_session, _ = fake_open_session(json.dumps(body))
    # 実行
    result = asyncio.run(
        fetch_used_tags(DEV_DOCS_URL, PROJECT_DIR, timeout=TIMEOUT, open_session=open_session)
    )
    # 検証
    assert result.tags == ("python",)
    assert result.reason is None


def test_fetch_used_tags_when_no_documents(
    fake_open_session: Callable[..., tuple[OpenSession, list[dict[str, Any]]]],
) -> None:
    """読める文書が 0 件なら飛ばす理由を返す（正常系）。"""
    from rule_inject.server.dev_docs import fetch_used_tags

    # 準備
    open_session, _ = fake_open_session(json.dumps({"total_count": 0, "returned": 0}))
    # 実行
    result = asyncio.run(
        fetch_used_tags(DEV_DOCS_URL, PROJECT_DIR, timeout=TIMEOUT, open_session=open_session)
    )
    # 検証
    assert result.tags == ()
    assert result.reason is not None
    assert DEV_DOCS_URL in result.reason
    assert "0 件" in result.reason


def test_fetch_used_tags_when_tool_error(
    fake_open_session: Callable[..., tuple[OpenSession, list[dict[str, Any]]]],
) -> None:
    """ツールのエラーを飛ばす理由にする（正常系）。"""
    from rule_inject.server.dev_docs import fetch_used_tags

    # 準備
    open_session, _ = fake_open_session("bad argument", is_error=True)
    # 実行
    result = asyncio.run(
        fetch_used_tags(DEV_DOCS_URL, PROJECT_DIR, timeout=TIMEOUT, open_session=open_session)
    )
    # 検証
    assert result.tags == ()
    assert result.reason is not None
    assert DEV_DOCS_URL in result.reason
    assert "bad argument" in result.reason


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("not json", id="not_json"),
        pytest.param(json.dumps({"groups": []}), id="no_total_count"),
    ],
)
def test_fetch_used_tags_when_unreadable(
    fake_open_session: Callable[..., tuple[OpenSession, list[dict[str, Any]]]],
    text: str,
) -> None:
    """読めない応答を飛ばす理由にする（正常系）。"""
    from rule_inject.server.dev_docs import fetch_used_tags

    # 準備
    open_session, _ = fake_open_session(text)
    # 実行
    result = asyncio.run(
        fetch_used_tags(DEV_DOCS_URL, PROJECT_DIR, timeout=TIMEOUT, open_session=open_session)
    )
    # 検証
    assert result.tags == ()
    assert result.reason is not None
    assert DEV_DOCS_URL in result.reason
    assert "読めない" in result.reason


def test_fetch_used_tags_when_timeout(
    fake_open_session: Callable[..., tuple[OpenSession, list[dict[str, Any]]]],
) -> None:
    """待ち時間の上限を超えたら飛ばす理由を返す（正常系）。"""
    from rule_inject.server.dev_docs import fetch_used_tags

    # 準備
    open_session, _ = fake_open_session(json.dumps({"total_count": 1, "groups": []}), delay=1)
    # 実行
    result = asyncio.run(
        fetch_used_tags(DEV_DOCS_URL, PROJECT_DIR, timeout=0.01, open_session=open_session)
    )
    # 検証
    assert result.tags == ()
    assert result.reason is not None
    assert DEV_DOCS_URL in result.reason
    assert "0.01" in result.reason


def test_fetch_used_tags_when_unreachable() -> None:
    """接続できないときは飛ばす理由を返す（正常系）。"""
    from rule_inject.server.dev_docs import fetch_used_tags

    # 準備: 接続先のポートは、SO_REUSEADDR を付けずに bind して listen しないまま握る
    # （接続は拒否され、呼び終わるまで他のプロセスはそのポートで待ち受けられない）
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{held.getsockname()[1]}/mcp"
        # 実行
        result = asyncio.run(fetch_used_tags(url, PROJECT_DIR, timeout=TIMEOUT))
    # 検証
    assert result.tags == ()
    assert result.reason is not None
    assert url in result.reason
    assert "接続できな" in result.reason
