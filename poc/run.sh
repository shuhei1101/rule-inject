#!/usr/bin/env bash
# Read と MCP のツールを claude -p で呼び、PostToolUse の入力を JSONL へ書き出す
set -euo pipefail

cd "$(dirname "$0")"
POC_DIR="$PWD"
OUT_DIR="${POC_OUT_DIR:-$POC_DIR/out}"
FIX_DIR="$OUT_DIR/fixtures"
mkdir -p "$FIX_DIR"
export POC_DUMP_PATH="$OUT_DIR/dump.jsonl"
: > "$POC_DUMP_PATH"

# Read の 6 通りに使うファイルを作る
python3 - "$FIX_DIR" <<'PY'
import sys
from pathlib import Path

d = Path(sys.argv[1])
(d / "short.txt").write_text("".join(f"short {n}\n" for n in range(1, 11)), encoding="utf-8")
(d / "long.txt").write_text("".join(f"long {n}\n" for n in range(1, 3001)), encoding="utf-8")
(d / "longline.txt").write_text("a\n" + "x" * 5000 + "\nb\n", encoding="utf-8")
(d / "huge.txt").write_text("".join(f"{n:05d} " + "y" * 300 + "\n" for n in range(1, 1501)), encoding="utf-8")
PY

cat > "$OUT_DIR/settings.json" <<JSON
{"hooks": {"PostToolUse": [{"matcher": "Read|mcp__.*", "hooks": [{"type": "command", "command": "python3 $POC_DIR/hook_dump.py"}]}]}}
JSON

cat > "$OUT_DIR/mcp.json" <<JSON
{"mcpServers": {"pocdocs": {"command": "uv", "args": ["run", "--project", "$POC_DIR/..", "python", "$POC_DIR/server.py"]}}}
JSON

claude --version | tee "$OUT_DIR/version.txt"

PROMPT="次のツールを、この順に 1 回ずつ呼んでください。結果の説明は要りません。
1. Read file_path=$FIX_DIR/short.txt
2. Read file_path=$FIX_DIR/short.txt offset=3 limit=2
3. Read file_path=$FIX_DIR/short.txt offset=5 limit=100
4. Read file_path=$FIX_DIR/long.txt
5. Read file_path=$FIX_DIR/longline.txt
6. Read file_path=$FIX_DIR/huge.txt
7. mcp__pocdocs__small_markdown
8. mcp__pocdocs__small_json
9. mcp__pocdocs__large_markdown
10. mcp__pocdocs__large_json"

claude -p "$PROMPT" \
    --settings "$OUT_DIR/settings.json" \
    --mcp-config "$OUT_DIR/mcp.json" --strict-mcp-config \
    --allowedTools "Read" "mcp__pocdocs__small_markdown" "mcp__pocdocs__small_json" "mcp__pocdocs__large_markdown" "mcp__pocdocs__large_json" \
    2>&1 | tee "$OUT_DIR/claude.log"
EXIT_CODE=${PIPESTATUS[0]}

echo "(dump: $POC_DUMP_PATH)"
echo "(exit: $EXIT_CODE)"
exit "$EXIT_CODE"
