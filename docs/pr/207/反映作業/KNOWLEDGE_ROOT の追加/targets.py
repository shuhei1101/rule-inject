"""KNOWLEDGE_ROOT の追加の対象: エージェントが使う認証領域ごとの settings.json と書き込む値。"""

from pathlib import Path

HOME = Path("/home/shuhei2441")
# env を持ち、エージェントのセッションが CLAUDE_CONFIG_DIR にする認証領域
SETTINGS_FILES = (
    HOME / ".claude" / "settings.json",
    HOME / ".claude-dev" / "settings.json",
    HOME / ".claude-dev1" / "settings.json",
    HOME / ".claude-sub" / "settings.json",
    HOME / ".claude-sub2" / "settings.json",
    HOME / ".claude-sub3" / "settings.json",
    HOME / ".claude-sub4" / "settings.json",
    HOME / ".claude-sub5" / "settings.json",
    HOME / ".claude-sub6" / "settings.json",
    HOME / ".claude-sub7" / "settings.json",
)
KEY = "KNOWLEDGE_ROOT"
VALUE = "/home/shuhei2441/repo/knowledge/.claude/worktrees/develop"
# 実行が取る退避の名前の末尾（切り戻しはこの末尾の退避だけを書き戻す）
BACKUP_SUFFIX = "knowledge-root"
