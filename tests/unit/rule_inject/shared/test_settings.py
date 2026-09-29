"""shared/settings.py の単体テスト。"""

from __future__ import annotations

import pytest

from rule_inject.shared import settings

LOG_ENV_NAME = "RULE_INJECT_LOG_RETENTION_DAYS"


def test_read_retention_days() -> None:
    """環境変数の整数を返す（正常系）。"""
    # 実行
    result = settings.read_retention_days({LOG_ENV_NAME: "7"}, LOG_ENV_NAME, 3)
    # 検証
    assert result == 7


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({}, id="missing"),
        pytest.param({LOG_ENV_NAME: ""}, id="empty"),
    ],
)
def test_read_retention_days_when_missing(env: dict[str, str]) -> None:
    """環境変数が無いか空なら既定を返す（正常系）。"""
    # 実行
    result = settings.read_retention_days(env, LOG_ENV_NAME, 3)
    # 検証
    assert result == 3


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("0", id="zero"),
        pytest.param("-1", id="negative"),
        pytest.param("abc", id="not_number"),
        pytest.param("1.5", id="decimal"),
    ],
)
def test_read_retention_days_when_invalid(value: str) -> None:
    """1 以上の整数でなければ既定を返す（正常系）。"""
    # 実行
    result = settings.read_retention_days({LOG_ENV_NAME: value}, LOG_ENV_NAME, 3)
    # 検証
    assert result == 3
