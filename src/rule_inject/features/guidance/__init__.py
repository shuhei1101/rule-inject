"""フックが返す案内文の組み立て。"""

from rule_inject.features.guidance.service import (
    BLOCKING_HEADER,
    GUIDANCE_LIMIT,
    NON_BLOCKING_HEADER,
    READ_NOTE,
    READ_TOOL_NOTE,
    SEARCH_HEADER,
    SERVER_START_NOTICE,
    build_failure_notice,
    build_guidance,
    build_search_guidance,
    build_server_start_notice,
)
from rule_inject.features.guidance.types import Guidance, GuidedReadTool, GuidedRule

__all__ = [
    "BLOCKING_HEADER",
    "GUIDANCE_LIMIT",
    "NON_BLOCKING_HEADER",
    "READ_NOTE",
    "READ_TOOL_NOTE",
    "SEARCH_HEADER",
    "SERVER_START_NOTICE",
    "Guidance",
    "GuidedReadTool",
    "GuidedRule",
    "build_failure_notice",
    "build_guidance",
    "build_search_guidance",
    "build_server_start_notice",
]
