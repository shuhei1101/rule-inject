"""MCP のツールの結果に載った文書の場所と範囲の取り出し。"""

from rule_inject.features.document.service import extract_documents
from rule_inject.features.document.types import DocumentScope, ResultDocument

__all__ = ["DocumentScope", "ResultDocument", "extract_documents"]
