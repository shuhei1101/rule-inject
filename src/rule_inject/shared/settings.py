"""保持の日数の環境変数の読み取り。"""

from __future__ import annotations

import re
from collections.abc import Mapping

# 既読の記録の保持日数を上書きする環境変数と、無いときの日数
RECORD_RETENTION_DAYS_ENV = "RULE_INJECT_RECORD_RETENTION_DAYS"
DEFAULT_RECORD_RETENTION_DAYS = 30
# ログの保持日数を上書きする環境変数と、無いときの日数
LOG_RETENTION_DAYS_ENV = "RULE_INJECT_LOG_RETENTION_DAYS"
DEFAULT_LOG_RETENTION_DAYS = 3
# 10 進の整数の書き方（符号は付けてよい）
INTEGER_PATTERN = re.compile(r"[+-]?[0-9]+")


def read_retention_days(env: Mapping[str, str], name: str, default: int) -> int:
    """環境変数から 1 以上の保持の日数を読み、読めなければ既定の日数を返す。"""
    text = env.get(name, "").strip()
    # 無い・空・整数として読めない値は、利用者が決めた扱いで既定の日数にする
    if not INTEGER_PATTERN.fullmatch(text):
        return default
    days = int(text)
    # 0 以下は保持の日数にならないため既定の日数にする
    return days if days >= 1 else default
