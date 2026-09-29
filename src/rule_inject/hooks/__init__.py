"""Claude Code が呼ぶフックの入口。run.py の引数の名前から、処理と知らせ方を引く。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rule_inject.hooks._runner import HookHandler, UnexpectedNotifier
from rule_inject.hooks.discard_read import discard_read
from rule_inject.hooks.record_read import record_read
from rule_inject.hooks.rule_guide import guide_rules
from rule_inject.hooks.session_id_injection import inject_session_id
from rule_inject.hooks.sweep_read import sweep_read
from rule_inject.hooks.work_rules import work_rules
from rule_inject.shared.logger import Component


def _notice_of(event: str, subject: str) -> UnexpectedNotifier:
    """想定外の例外を、additionalContext で知らせる関数を作る。"""

    def _notify(message: str, log_path: Path) -> dict[str, Any]:
        """何が動かなかったかと、ログの場所を知らせる。"""
        text = (
            f"{subject}が動きませんでした（{message}）。詳しくはログ（{log_path}）を見てください。"
        )
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}

    return _notify


def _silent(message: str, log_path: Path) -> None:
    """想定外の例外を何も出力せずに終える。"""
    return


# run.py の引数の名前 → 出した元・処理・想定外の例外の知らせ方
HOOKS: dict[str, tuple[Component, HookHandler, UnexpectedNotifier]] = {
    "rule_guide": (Component.RULE_GUIDE, guide_rules, _notice_of("PreToolUse", "ルールの案内")),
    "session_id_injection": (Component.SESSION_ID_INJECTION, inject_session_id, _silent),
    "record_read": (Component.RECORD_READ, record_read, _notice_of("PostToolUse", "既読の記録")),
    "discard_read": (Component.DISCARD_READ, discard_read, _silent),
    "work_rules": (Component.WORK_RULES, work_rules, _silent),
    "sweep_read": (Component.SWEEP_READ, sweep_read, _silent),
}
