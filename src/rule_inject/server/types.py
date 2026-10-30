"""サーバーの型（応答の形式・ツールの応答のモデル）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

from rule_inject.features.index.types import Operation
from rule_inject.features.record.types import ReadMethod, ReadState

# 読むツールの `format`
type ResponseFormat = Literal["markdown", "json"]
# 使われていないタグのパターンの確かめの結果（確かめた・dev-docs に届かず飛ばした・確かめるパターンが無い）
type TagCheckState = Literal["checked", "skipped", "no_patterns"]


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
    # 索引の出所。`global` は `global.indexes`（無ければユーザーの既定の索引）、`project` はプロジェクトの索引
    origin: Literal["global", "project"]
    hook_error: str | None
    violations: list[dict[str, str]]
    missing_rules: list[dict[str, Any]]
    skipped_entries: list[dict[str, Any]]
    unmatched_paths: list[dict[str, Any]]
    # 使われているどのタグにも当たらないタグのパターン（`global` と `project` のどちらの索引も載せる）
    unused_tag_patterns: list[dict[str, Any]] = Field(default_factory=list)


class UnmatchedScanReport(BaseModel):
    """`paths` の当たらないエントリの検出の状態。"""

    completed: bool
    scanned_files: int
    # 終えられなかった理由（辿る時間の上限の秒数と `cursor` の使い方）
    reason: str | None
    next_cursor: str | None


class TagCheckReport(BaseModel):
    """使われていないタグのパターンの確かめの結果。"""

    state: TagCheckState
    # `skipped` のときの、飛ばした理由。それ以外は None
    reason: str | None


class CheckIndexesResult(BaseModel):
    """索引のチェックの応答。"""

    success: bool
    output: str
    config_path: str | None
    problem_count: int
    unmatched_scan: UnmatchedScanReport
    tag_check: TagCheckReport = Field(
        default_factory=lambda: TagCheckReport(state="no_patterns", reason=None)
    )
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


class ReadSummary(BaseModel):
    """読み方とツールの組ごとの既読のまとめ。"""

    method: ReadMethod
    tool: str
    # その読み方とツールで最後に既読にした時刻（既読の履歴の `time` のまま）
    last_time: str
    count: int


class RuleRead(BaseModel):
    """既読のルール。"""

    location: str
    state: ReadState
    reads: list[ReadSummary]


class RecordSessionItem(BaseModel):
    """既読の記録のあるセッション。"""

    session_id: str
    # 既読の記録のファイルの最終更新の時刻（UTC）
    updated_at: str
    rule_count: int


class ReadRecordsResult(BaseModel):
    """既読の記録の確認の応答。"""

    success: bool
    output: str
    config_path: str | None
    state_dir: str
    session_id: str | None
    rules: list[RuleRead]
    sessions: list[RecordSessionItem]
    total: int
    next_cursor: str | None


class DeleteRecordsResult(BaseModel):
    """既読の記録の削除の応答。"""

    success: bool
    output: str
    config_path: str | None
    state_dir: str
    session_id: str
    locations: list[str]
