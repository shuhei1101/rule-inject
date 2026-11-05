"""設定の移し替えの結果と誤りの型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class MigrationResult:
    """移し替えの手順の算出・適用の結果。"""

    # 設定ファイルの `version`。ファイルかキーが無いときは None
    source_version: str | None
    # ツールのバージョン。移し替え後の `version`
    target_version: str
    steps: tuple[str, ...]
    # 書き換えなかったときは None
    backup: str | None
    # `settings.json` の `env` へ移す環境変数の名前と値
    env: dict[str, str]


class SettingsNewerError(Exception):
    """設定ファイルの `version` がツールのバージョンより新しい。"""

    def __init__(self, *, settings_version: str, tool_version: str) -> None:
        """比べた 2 つのバージョンから文面を作る。"""
        super().__init__(f"設定 {settings_version} はツール {tool_version} より新しい")
        self.settings_version = settings_version
        self.tool_version = tool_version
