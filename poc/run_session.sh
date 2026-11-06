#!/usr/bin/env bash
# 対話モードの claude を 1 回起動し、サーバーの待ち受けの開始と MCP の接続の時刻を記録する。
# 使い方: run_session.sh {plugin-hook|plugin-hook-alwaysload|plugin-nohook} {回の番号}
set -euo pipefail

VARIANT="$1"
RUN="$2"
POC_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKTREE="$(dirname "$POC_DIR")"
OUT=/tmp/poc112
PORT="$(cat "$OUT/port")"
SERVICE=rule-inject-poc-112.service
SESSION=rule-inject-poc-112-claude
TAG="$VARIANT-$RUN"
DEBUG_FILE="$OUT/$TAG.debug.log"
RESULT="$OUT/$TAG.result.json"
# 観測の窓。接続の待ちの上限 30 秒に 15 秒を加え、失敗の表示まで含める
OBSERVE_SECONDS=45

# サーバーを止め、ポートが空くまで待つ
systemctl --user stop "$SERVICE"
until ! ss -ltnH "( sport = :$PORT )" | grep -q .; do sleep 0.2; done
tmux has-session -t "=$SESSION" 2>/dev/null && tmux kill-session -t "=$SESSION"
rm -f "$DEBUG_FILE"

# セッションを開始する
start=$(date +%s.%N)
tmux new-session -d -s "$SESSION" -x 200 -y 50 -c "$WORKTREE" \
  -e "RULE_INJECT_PORT=$PORT" -e "RULE_INJECT_POC_LOG=$OUT/hook.jsonl" \
  "claude --plugin-dir $POC_DIR/$VARIANT --debug-file $DEBUG_FILE"

# 観測の窓の間、待ち受けの開始の時刻を記録する
listen=null
while :; do
  now=$(date +%s.%N)
  if [ "$listen" = null ] && ss -ltnH "( sport = :$PORT )" | grep -q .; then
    listen=$now
  fi
  if (( $(echo "$now - $start > $OBSERVE_SECONDS" | bc) )); then break; fi
  sleep 0.2
done

# /mcp の表示を残す
tmux send-keys -t "=$SESSION:" "/mcp" Enter
sleep 2
tmux capture-pane -p -t "=$SESSION:" -S -60 > "$OUT/$TAG.mcp.txt"
tmux send-keys -t "=$SESSION:" Escape
tmux kill-session -t "=$SESSION"
systemctl --user stop "$SERVICE"

printf '{"variant": "%s", "run": %s, "start": %s, "listen": %s}\n' "$VARIANT" "$RUN" "$start" "$listen" > "$RESULT"
cat "$RESULT"
