"""フックの起動。src/ を import の探索に追加し、引数で指したフックを動かす。

Usage:
python3 hooks/run.py rule_guide
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# フックの Python の最低のバージョン（これより古い python3 ではパッケージを import しない）
MIN_PYTHON = (3, 12)
# バージョンが足りないことを知らせられる出来事（ほかの出来事は additionalContext を持たない）
NOTICE_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart")
# バージョンが足りなくても知らせを返さないフック
SILENT_HOOK = "sweep_read"
LOG_FILE_SUFFIX = "_rule-inject.log"


def _log_dir() -> Path:
    """既定のログのフォルダを決める（設定ファイルは読まない。パッケージを使わない、古いバージョンでも読める書き方）。"""
    state_home = os.environ.get("XDG_STATE_HOME") or "~/.local/state"
    return Path(state_home).expanduser() / "rule-inject" / "logs"


def _report_old_python(hook_name: str) -> int:
    """バージョンが足りないことを知らせ、ログへ 1 行書いて終える。"""
    major, minor, micro = sys.version_info[:3]
    required = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    reason = (
        f"フックには Python {required} 以上が要ります（動いた python3 は {major}.{minor}.{micro}）"
    )
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    event = payload.get("hook_event_name") if isinstance(payload, dict) else None
    # ログへ書けなければ、同じ 1 行を標準エラー出力へ出す
    # datetime.UTC は 3.11 以降のため、古いバージョンでも読める timezone.utc を使う
    now = datetime.now(timezone.utc)  # noqa: UP017
    line = json.dumps(
        {
            "time": now.isoformat(),
            "component": hook_name,
            "session_id": session_id,
            "operation": "unexpected",
            "path": sys.executable,
            "reason": reason,
        },
        ensure_ascii=False,
    )
    try:
        folder = _log_dir()
        folder.mkdir(parents=True, exist_ok=True)
        # 今日（UTC）の日付のログのファイルに書く
        with (folder / f"{now:%Y%m%d}{LOG_FILE_SUFFIX}").open("a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
    except OSError:
        print(line, file=sys.stderr)
    # additionalContext を持てる出来事にだけ知らせる（PreCompact などは黙って終える）
    # sweep_read は同じ SessionStart の work_rules が知らせるため、知らせを重ねない
    if event in NOTICE_EVENTS and hook_name != SILENT_HOOK:
        output = {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": reason + "。"}
        }
        print(json.dumps(output))
    return 0


def main(argv: list[str]) -> int:
    """引数で指したフックを動かして終了コードを返す（常に 0）。"""
    if tuple(sys.version_info[:2]) < MIN_PYTHON:
        return _report_old_python(argv[0])
    # バージョンを確かめた後で、同梱のパッケージを import できるようにする
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from rule_inject.hooks import HOOKS
    from rule_inject.hooks._runner import run_hook

    component, handle, on_unexpected = HOOKS[argv[0]]
    return run_hook(component, handle, on_unexpected)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
