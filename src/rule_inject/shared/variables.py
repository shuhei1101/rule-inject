"""`!{名前}` を環境変数の値へ展開する。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

# `!{名前}` の正規表現（名前をグループで取る）
VARIABLE_PATTERN = re.compile(r"!\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True, slots=True, kw_only=True)
class Expansion:
    """変数参照の展開の結果。"""

    # 設定された名前を値に置き換え、未設定の名前を `!{名前}` のまま残した文字列
    text: str
    # 未設定の名前（重なりを落とし、出た順）
    unresolved: tuple[str, ...]


def expand_variables(text: str, env: Mapping[str, str]) -> Expansion:
    """文字列の `!{名前}` を環境変数の値に置き換え、展開できなかった名前と一緒に返す。"""
    unresolved: list[str] = []

    def _replace(matched: re.Match[str]) -> str:
        """設定された名前は値に、無い名前はそのまま残して控える。"""
        name = matched.group(1)
        if name in env:
            return env[name]
        unresolved.append(name)
        return matched.group(0)

    # 1 回の置き換えで前から順に展開する（置き換えた値の中の参照は展開し直さない）
    expanded = VARIABLE_PATTERN.sub(_replace, text)
    return Expansion(text=expanded, unresolved=tuple(dict.fromkeys(unresolved)))
