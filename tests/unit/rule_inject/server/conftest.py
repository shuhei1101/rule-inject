"""server の単体テストが共有する fixture。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def server_env(
    tmp_path: Path,
    make_settings: Callable[..., Path],
) -> Callable[..., dict[str, str]]:
    """設定ファイルを記載して `RULE_INJECT_CONFIG` で指した、サーバーを起動した環境変数を返却する factory。"""

    def _make(text: str) -> dict[str, str]:
        """text を設定ファイルに書き込み、それを指す環境変数を返却する。"""
        config = make_settings(text)
        return {"RULE_INJECT_CONFIG": str(config)}

    return _make


@pytest.fixture
def indexes_env(server_env: Callable[..., dict[str, str]]) -> Callable[..., dict[str, str]]:
    """`global.indexes` に絶対パスの索引を並べた設定ファイルを指す環境変数を返却する factory。"""

    def _make(*indexes: Path) -> dict[str, str]:
        """indexes を `global.indexes` に並べる。"""
        lines = ["global:", "  indexes:"]
        lines.extend(f"    - {index}" for index in indexes)
        return server_env("\n".join(lines) + "\n")

    return _make
