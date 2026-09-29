"""索引に載ったルールの本文の取得（読み込み・応答の上限・既読の記録）。"""

from rule_inject.features.fetch.client import FETCH_TIMEOUT_SEC, FetchError, fetch_url
from rule_inject.features.fetch.service import (
    MAX_RESULT_CHARS,
    ToolArgumentError,
    read_rules,
    render_result,
)
from rule_inject.features.fetch.types import (
    FetchFailure,
    FetchUrlFn,
    ReadRulesResult,
    RulePage,
)

__all__ = [
    "FETCH_TIMEOUT_SEC",
    "MAX_RESULT_CHARS",
    "FetchError",
    "FetchFailure",
    "FetchUrlFn",
    "ReadRulesResult",
    "RulePage",
    "ToolArgumentError",
    "fetch_url",
    "read_rules",
    "render_result",
]
