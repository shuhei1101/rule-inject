#!/bin/sh
set -eu

LINK=/home/shuhei2441/.local/bin/rule-inject-validate-entry

FOUND=$(command -v rule-inject-validate-entry || true)
if [ "$FOUND" = "$LINK" ]; then
  echo "コマンドの場所: ok（$FOUND）"
else
  echo "コマンドの場所: failed（${FOUND:-見つからない}）"
  exit 1
fi
CODE=0
OUT=$(echo '{}' | rule-inject-validate-entry --index rules.yaml) || CODE=$?
if [ "$CODE" = 0 ]; then
  echo "空のエントリの検査: ok（$OUT）"
else
  echo "空のエントリの検査: failed（終了コード $CODE）"
  exit 1
fi
