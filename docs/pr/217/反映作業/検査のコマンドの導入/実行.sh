#!/bin/sh
set -eu

CLONE=/home/shuhei2441/repo/rule-inject/.claude/worktrees/develop
EXE=/home/shuhei2441/repo/rule-inject/.claude/worktrees/develop/.venv/bin/rule-inject-validate-entry
LINK=/home/shuhei2441/.local/bin/rule-inject-validate-entry

# 前提確認
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--dry-run" ]; }; then
  echo "前提確認: failed"
  exit 1
fi
if [ ! -f "$CLONE/pyproject.toml" ]; then
  echo "前提確認: failed"
  exit 1
fi
if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "前提確認: failed"
  echo "リンクでないファイルがある: $LINK"
  exit 1
fi
echo "前提確認: ok"

# 計画
if [ -x "$EXE" ]; then
  echo "依存の同期: skipped"
  NEED_SYNC=0
else
  echo "依存の同期: changed（cd $CLONE && uv sync --extra server）"
  NEED_SYNC=1
fi
if [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$EXE" ]; then
  echo "リンクの作成: skipped"
  NEED_LINK=0
else
  echo "--- /dev/null"
  echo "+++ $LINK -> $EXE"
  echo "リンクの作成: changed"
  NEED_LINK=1
fi
if [ "${1:-}" = "--dry-run" ]; then
  exit 0
fi

# 適用
if [ "$NEED_SYNC" = 1 ]; then
  if ! (cd "$CLONE" && uv sync --extra server); then
    echo "依存の同期: failed"
    echo "cd $CLONE && uv sync --extra server"
    exit 1
  fi
  if [ ! -x "$EXE" ]; then
    echo "依存の同期: failed"
    echo "$EXE が作られていない"
    exit 1
  fi
fi
if [ "$NEED_LINK" = 1 ]; then
  ln -sfn "$EXE" "$LINK"
fi
echo "完了: ok"
