"""URL の本文の取得（urllib）。"""

from __future__ import annotations

import urllib.error
import urllib.request
from http import HTTPStatus

from rule_inject.shared.errors import RuleInjectError, describe

# URL 1 件あたりの待ち時間（秒）
FETCH_TIMEOUT_SEC = 1.0
HTTPS_SCHEME = "https://"


class FetchError(RuleInjectError):
    """HTTP の応答コード・待ち時間の超過・接続の失敗。"""


def _timeout_reason(timeout: float) -> str:
    """待ち時間の超過の理由の文面を返す。"""
    return f"待ち時間（{timeout} 秒）の超過"


def fetch_url(url: str, timeout: float = FETCH_TIMEOUT_SEC) -> str:
    """URL を 1 回だけ GET して本文を返す（再試行しない）。"""
    # 平文の通信で取得したルールは案内に使わない
    if not url.startswith(HTTPS_SCHEME):
        raise FetchError(path=url, reason="HTTPS でない URL は取得しない")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(path=url, reason=f"HTTP {exc.code}") from exc
    except TimeoutError as exc:
        raise FetchError(path=url, reason=_timeout_reason(timeout)) from exc
    except urllib.error.URLError as exc:
        # 接続中の待ち時間の超過は URLError に包まれて届く
        if isinstance(exc.reason, TimeoutError):
            raise FetchError(path=url, reason=_timeout_reason(timeout)) from exc
        raise FetchError(path=url, reason=describe(exc)) from exc
    except OSError as exc:
        raise FetchError(path=url, reason=describe(exc)) from exc
    if status != HTTPStatus.OK:
        raise FetchError(path=url, reason=f"HTTP {status}")
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FetchError(path=url, reason="UTF-8 として読めない本文") from exc
