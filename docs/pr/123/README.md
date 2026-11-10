# 再起動の停止の待ちで、ツールの応答を送信し終えるまで待ち受けを閉じない

## 概要

Claude Code が常駐の MCP サーバーの再起動・更新のツールを呼んだとき、応答を受け取ってからサーバーが待ち受けを閉じるようにする。

## 背景

[Issue #121](https://github.com/shuhei1101/rule-inject/issues/121) の不具合。
結合テスト `tests/integration/server/test_update_server.py::test_normal` で、`update_server` の呼び出しが `SSE stream ended without a response` でときどき失敗する。
停止の待ち（`ServerControl._drain_and_stop`）は、ツールの関数が戻った時点で処理中の呼び出しが終わったとみなし、応答を送信し終える前に待ち受けを閉じることがある。
停止の待ちは [PR #110](https://github.com/shuhei1101/rule-inject/pull/110) で追加した、v0.3.0 で初めてリリースする機能。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
