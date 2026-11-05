"""features/migrate/migrations/v0_2_3.py の単体テスト。"""

from __future__ import annotations

from typing import Any

import pytest

from rule_inject.features.migrate.migrations import v0_2_3


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param({"global": {"server_port": 9000}}, True, id="has_key"),
        pytest.param({"global": {"log_dir": "/a"}}, False, id="no_key"),
        pytest.param({}, False, id="no_global"),
    ],
)
def test_applies(data: dict[str, Any], expected: bool) -> None:
    """キーの有無を返却する（正常系）。"""
    # 実行
    result = v0_2_3.applies(data)
    # 検証
    assert result is expected


def test_apply() -> None:
    """ポートの値を返却する（正常系）。"""
    # 準備
    data: dict[str, Any] = {"global": {"server_port": 9000}}
    # 実行
    result = v0_2_3.apply(data)
    # 検証
    assert result == {"RULE_INJECT_PORT": "9000"}
    assert data == {"global": {}}


def test_apply_when_default() -> None:
    """既定のポートは返却しない（正常系）。"""
    # 準備
    data: dict[str, Any] = {"global": {"server_port": 8783}}
    # 実行
    result = v0_2_3.apply(data)
    # 検証
    assert result == {}
    assert data == {"global": {}}
