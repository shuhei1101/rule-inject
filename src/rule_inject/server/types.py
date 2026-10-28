"""サーバーの型（応答の形式・ツールの応答のモデル）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_serializer

from rule_inject.features.index.types import Operation

# 読むツールの `format`
type ResponseFormat = Literal["markdown", "json"]


class RuleEntry(BaseModel):
    """効いているエントリ。"""

    index: str
    position: int
    rev: str
    rule: str
    paths: list[str]
    exclude: list[str]
    tools: list[str]
    args: dict[str, list[str]]
    on: list[Operation]
    read_by: list[dict[str, Any]]


class IndexIssue(BaseModel):
    """読めない索引。"""

    index: str
    reason: str


class EntryIssue(BaseModel):
    """照合に使わないエントリ（読み飛ばした・無効）。"""

    index: str
    position: int
    rev: str
    rule: str
    # 読み飛ばした理由。無効のエントリでは応答に含めない
    reason: str | None = None

    @model_serializer(mode="wrap")
    def _drop_empty_reason(self, handler: Any) -> dict[str, Any]:
        """`reason` が無いとき（無効のエントリ）は応答から外す。"""
        data: dict[str, Any] = handler(self)
        if data.get("reason") is None:
            data.pop("reason", None)
        return data


class ListRulesResult(BaseModel):
    """ルールの一覧の応答。"""

    success: bool
    output: str
    config_path: str | None
    indexes: list[str]
    entries: list[RuleEntry]
    unreadable_indexes: list[IndexIssue]
    skipped_entries: list[EntryIssue]
    disabled_entries: list[EntryIssue]
    total: int
    next_cursor: str | None


class EntryRef(BaseModel):
    """エントリの場所。"""

    index: str
    position: int


class RuleMatch(BaseModel):
    """当たったルール。"""

    rule: str
    blocking: bool
    entries: list[EntryRef]


class SearchRulesResult(BaseModel):
    """ルールの検索の応答。"""

    success: bool
    output: str
    config_path: str | None
    operation: Operation
    matched: list[RuleMatch]
    unreadable_indexes: list[IndexIssue]
    skipped_entries: list[EntryIssue]


class IndexReport(BaseModel):
    """索引ごとのチェックの結果。"""

    index: str
    hook_error: str | None
    violations: list[dict[str, str]]
    missing_rules: list[dict[str, Any]]
    skipped_entries: list[dict[str, Any]]


class CheckIndexesResult(BaseModel):
    """索引のチェックの応答。"""

    success: bool
    output: str
    config_path: str | None
    problem_count: int
    indexes: list[IndexReport]


class WriteEntryResult(BaseModel):
    """エントリの書き込みの応答。"""

    success: bool
    output: str
    index: str
    position: int
    rev: str
    written: bool
    diff: str


class DeleteEntryResult(BaseModel):
    """エントリの削除の応答。"""

    success: bool
    output: str
    index: str
    rule: str
    written: bool
    diff: str
