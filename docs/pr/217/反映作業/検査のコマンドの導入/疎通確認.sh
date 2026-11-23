#!/bin/sh
set -eu

CLONE=/home/shuhei2441/repo/rule-inject/.claude/worktrees/develop
BIN=/home/shuhei2441/.local/bin

if [ -f "$CLONE/pyproject.toml" ] && grep -q '^rule-inject-validate-entry' "$CLONE/pyproject.toml"; then
  echo "MCP サーバーのクローン: ok"
else
  echo "MCP サーバーのクローン: failed"
  exit 1
fi
if command -v uv >/dev/null 2>&1; then
  echo "uv: ok"
else
  echo "uv: failed"
  exit 1
fi
if [ -d "$BIN" ] && [ "$(uv tool dir --bin)" = "$BIN" ]; then
  echo "uv tool dir --bin: ok"
else
  echo "uv tool dir --bin: failed"
  echo "uv tool dir --bin -> $(uv tool dir --bin 2>&1)"
  exit 1
fi
