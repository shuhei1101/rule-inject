# dev-docs の文書の MCP のツールの完全名と check_indexes の接続先の既定値を、project-index へ書き換える

## 概要

索引・公開ドキュメントに記載した dev-docs の文書の MCP のツールの完全名と、`check_indexes` が使用中のタグを取得する接続先の既定値を、project-index のプラグインと待ち受けへ書き換える。

## 背景

[Issue #158](https://github.com/shuhei1101/rule-inject/issues/158) の要望。
[shuhei1101/project-index#15](https://github.com/shuhei1101/project-index/pull/15) で、dev-docs の文書の MCP・管理の MCP が project-index のプラグイン `project-index` へ移り、待ち受けが既定のポート 8786 の `/mcp` になった。
[shuhei1101/dev-docs#163](https://github.com/shuhei1101/dev-docs/pull/163) で dev-docs から文書の MCP が除外されると、rule-inject の索引の `tool` はヒットしなくなり、`check_indexes` のタグの検査は dev-docs に届かず飛ばし続ける。
dev-docs#163 の反映作業は端末の Claude Code の接続先だけを付け替え、rule-inject の既定値は付け替えない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [MCPサーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
