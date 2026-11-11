"""サーバーの型（応答の形式・ツールの応答のモデル）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

from rule_inject.features.index.types import Operation
from rule_inject.features.record.types import ReadMethod, ReadState

# 読むツールの `format`
type ResponseFormat = Literal["markdown", "json"]
# 使用されていないタグのパターンの確認の結果（確認した・dev-docs に届かず飛ばした・確認するパターンが無い）
type TagCheckState = Literal["checked", "skipped", "no_patterns"]
# 更新の結果（何も変えなかった・取り込んで再起動を始めた・取り込んだが移し替えが要るため再起動しなかった）
type UpdateState = Literal["up_to_date", "restarting", "migration_required"]


class RuleEntry(BaseModel):
    """有効なエントリ。"""

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
    # 索引に書き込んだままの `read_tool`。記載しないエントリは None
    read_tool: dict[str, Any] | None = None


class IndexIssue(BaseModel):
    """読めない索引。"""

    index: str
    reason: str


class EntryIssue(BaseModel):
    """照合に使用しないエントリ（読み飛ばした・無効）。"""

    index: str
    position: int
    rev: str
    rule: str
    # 読み飛ばした理由。無効のエントリでは応答に含めない
    reason: str | None = None

    @model_serializer(mode="wrap")
    def _drop_empty_reason(self, handler: Any) -> dict[str, Any]:
        """`reason` が無いとき（無効のエントリ）は応答から除外する。"""
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
    """該当したルール。"""

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
    # 使用中のどのタグにも該当しないタグのパターン（`global` と `project` のどちらの索引も記載する）
    unused_tag_patterns: list[dict[str, Any]] = Field(default_factory=list)


class UnmatchedScanReport(BaseModel):
    """`paths` の該当しないエントリの検出の状態。"""

    completed: bool
    scanned_files: int
    # 終えられなかった理由（辿る時間の上限の秒数と `cursor` の使用方法）
    reason: str | None
    next_cursor: str | None


class TagCheckReport(BaseModel):
    """使用されていないタグのパターンの確認の結果。"""

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


class ConfigState(BaseModel):
    """設定ファイルを読めるか。"""

    # 読んだ設定ファイルの場所。既定のパスにファイルが無く読まなかったときは None
    path: str | None
    readable: bool
    # 読めなかった理由（場所と理由）
    error: str | None


class ServerStatusResult(BaseModel):
    """サーバーの状態の確認の応答。"""

    success: bool
    output: str
    port: int
    pid: int
    # 待ち受けを始めた時刻（UTC の ISO 8601）。再起動のたびに新しくなる
    started_at: str
    version: str | None
    clone: str
    # クローンの HEAD。git のリポジトリでないときは None
    commit: str | None
    config: ConfigState
    # 再起動を始めた後で、まだ待ち受けを閉じていないか
    restarting: bool


class ReloadSettingsResult(BaseModel):
    """設定の再読込の応答。"""

    success: bool
    output: str
    config_path: str | None
    indexes: list[str]
    state_dir: str
    record_retention_days: int
    log_retention_days: int
    dev_docs_url: str


class RestartResult(BaseModel):
    """サーバーの再起動の応答。"""

    success: bool
    output: str
    pid: int
    restarting: bool


class UpdateResult(BaseModel):
    """サーバーの更新の応答。"""

    success: bool
    output: str
    state: UpdateState
    before: str
    after: str
    # 照合する移し替えの手順。migration_required 以外は空
    steps: list[str]
