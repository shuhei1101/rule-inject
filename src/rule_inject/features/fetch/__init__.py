"""ルールの本文の読み込みと、応答の上限への収め方。"""

from rule_inject.features.fetch.client import FETCH_TIMEOUT_SEC, FetchError, fetch_url
from rule_inject.features.fetch.service import MAX_RESULT_CHARS, collect_pages, render_result
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
    "collect_pages",
    "fetch_url",
    "render_result",
]
