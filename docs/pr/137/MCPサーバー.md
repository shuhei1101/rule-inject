# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/external-api/API-122-1.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/external-api/API-122-1.yaml) | dev-docs の MCP サーバーの利用方法 | `notes`・`detail` に他リポジトリの Issue 番号（dev-docs#50）とソースのパスの生の文字がある |
| ドキュメント | [docs/library/](https://github.com/shuhei1101/rule-inject/blob/develop/docs/library/index.yaml) | jsonschema・mcp・ruamel.yaml・uvicorn・sse-starlette の利用方法（LIB-122-2〜6） | - |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 設計書の本文 | 要件.md の工程 1〜4 で移行する | - |
| 他リポジトリの Issue 番号とソースのパスの生の文字 | タイトル付きのリンクにする | API-122-1 |

## テスト結果

なし（設計書の本文だけを変え、コードを変えないため、関係する単体・結合テストが無い）
