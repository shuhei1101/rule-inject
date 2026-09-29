"""features/fetch/client.py の単体テスト。"""

from __future__ import annotations

import io
import urllib.error
from email.message import Message
from unittest.mock import MagicMock, patch

import pytest

from rule_inject.features.fetch.client import FetchError, fetch_url

URL = "https://example.com/rules/web.md"


@pytest.fixture
def ok_response() -> MagicMock:
    """200 と本文を返す urlopen の応答。"""
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.getcode.return_value = 200
    response.read.return_value = "# Web の規約\n".encode()
    return response


def test_fetch_url(ok_response: MagicMock) -> None:
    """本文を返す（正常系）。"""
    # 準備
    with patch("urllib.request.urlopen", return_value=ok_response) as urlopen:
        # 実行
        result = fetch_url(URL)
    # 検証
    assert result == "# Web の規約\n"
    assert urlopen.call_count == 1
    assert urlopen.call_args.kwargs["timeout"] == 1.0


def test_fetch_url_when_http_error() -> None:
    """404 を FetchError にして再試行しない（異常系）。"""
    # 準備
    error = urllib.error.HTTPError(URL, 404, "Not Found", Message(), io.BytesIO())
    # 実行・検証
    with (
        patch("urllib.request.urlopen", side_effect=error) as urlopen,
        pytest.raises(FetchError) as excinfo,
    ):
        fetch_url(URL)
    assert excinfo.value.reason == "HTTP 404"
    assert urlopen.call_count == 1


def test_fetch_url_when_timeout() -> None:
    """待ち時間の超過を FetchError にする（異常系）。"""
    # 実行・検証
    with (
        patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")),
        pytest.raises(FetchError) as excinfo,
    ):
        fetch_url(URL)
    assert "待ち時間" in excinfo.value.reason


def test_fetch_url_when_http() -> None:
    """平文の http:// は取得しない（異常系）。"""
    # 実行・検証
    with patch("urllib.request.urlopen") as urlopen, pytest.raises(FetchError) as excinfo:
        fetch_url("http://example.com/a.md")
    assert excinfo.value.reason == "HTTPS でない URL は取得しない"
    urlopen.assert_not_called()
