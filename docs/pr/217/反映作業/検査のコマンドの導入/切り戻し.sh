#!/bin/sh
set -eu

EXE=/home/shuhei2441/repo/rule-inject/.claude/worktrees/develop/.venv/bin/rule-inject-validate-entry
LINK=/home/shuhei2441/.local/bin/rule-inject-validate-entry

if [ ! -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "リンクの削除: skipped"
  exit 0
fi
if [ ! -L "$LINK" ] || [ "$(readlink "$LINK")" != "$EXE" ]; then
  echo "リンクの削除: skipped（$LINK は $EXE を指すリンクでない）"
  exit 0
fi
rm "$LINK"
echo "リンクの削除: changed"
