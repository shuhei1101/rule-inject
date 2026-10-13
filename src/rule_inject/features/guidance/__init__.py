"""フックが返す案内文の組み立て。"""

from rule_inject.features.guidance.service import (
    BLOCKING_HEADER,
    GUIDANCE_LIMIT,
    NON_BLOCKING_HEADER,
    SEARCH_HEADER,
    WORK_RULES,
    build_failure_notice,
    build_guidance,
    build_search_guidance,
)
from rule_inject.features.guidance.types import Guidance, GuidedRule

__all__ = [
    "BLOCKING_HEADER",
    "GUIDANCE_LIMIT",
    "NON_BLOCKING_HEADER",
    "SEARCH_HEADER",
    "WORK_RULES",
    "Guidance",
    "GuidedRule",
    "build_failure_notice",
    "build_guidance",
    "build_search_guidance",
]
