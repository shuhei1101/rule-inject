#!/usr/bin/env bash
# PoC の 5 回を流し、各回の claude -p の出力を poc/results/ に置く
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PLUGIN="$HERE/rule-inject-poc"
OUT="$HERE/results"
WORK="$(mktemp -d)"
TOOL="mcp__plugin_rule-inject-poc_poc__echo"
mkdir -p "$OUT"
rm -f "$PLUGIN/poc.log.jsonl"

ask_plain="ツール $TOOL を location に \"rules/sample-RUN.md\" を渡して 1 回だけ呼び、返ってきた JSON をそのまま出力してください。session_id は渡さないでください。"
ask_model="ツール $TOOL を location に \"rules/sample-RUN.md\"、session_id に \"model-supplied\" を渡して 1 回だけ呼び、返ってきた JSON をそのまま出力してください。"

run() {
  local n="$1" mode="$2" prompt="$3"; shift 3
  prompt="${prompt//RUN/$n}"
  (cd "$WORK" && POC_RUN="$n" POC_MODE="$mode" claude -p "$prompt" \
    --plugin-dir "$PLUGIN" --output-format json --max-turns 3 "$@" < /dev/null) > "$OUT/run$n.json" 2> "$OUT/run$n.stderr" || true
}

run 1 none "$ask_plain" --allowedTools "$TOOL"
run 2 none "$ask_model" --allowedTools "$TOOL"
run 3 none "$ask_plain" --allowedTools "$TOOL"
run 4 allow "$ask_plain"
run 5 ask "$ask_plain"
cp "$PLUGIN/poc.log.jsonl" "$OUT/poc.log.jsonl" 2>/dev/null || true
