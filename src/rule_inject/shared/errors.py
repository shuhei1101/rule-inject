"""設定ファイル・索引・既読の記録・既読の履歴・ログの読み書きの例外。"""

from __future__ import annotations


class RuleInjectError(Exception):
    """このプラグインが送出する例外の基底（失敗した場所と理由を持つ）。"""

    def __init__(self, path: str, reason: str) -> None:
        """失敗した操作の対象と理由から文面を作る。"""
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class SettingsReadError(RuleInjectError):
    """設定ファイルが無い・読めない・知らないキーや許す値の外の値を持つ。"""


class IndexReadError(RuleInjectError):
    """索引が無い・読めない・書式に合わない。"""


class RecordReadError(RuleInjectError):
    """記録ファイルはあるが読めない。"""


class RecordWriteError(RuleInjectError):
    """記録フォルダが作れない・記録ファイルに追記できない。"""


class HistoryWriteError(RuleInjectError):
    """記録フォルダが作れない・既読の履歴ファイルに追記できない。"""


class RecordDeleteError(RuleInjectError):
    """記録ファイルはあるが削除できない。"""


class LogDeleteError(RuleInjectError):
    """削除する対象のログのファイルはあるが削除できない。"""


def describe(exc: BaseException) -> str:
    """例外のクラス名と文面を 1 つの理由の文字列にする。"""
    return f"{type(exc).__name__}: {exc}"
