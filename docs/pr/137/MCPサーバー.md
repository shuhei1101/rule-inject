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

結合テストのコメント（`tests/integration/server/conftest.py` の `START_ATTEMPTS`）の参照を、テスト実行方法の補足のキーの変更（`起動し直す回数` → `再起動の回数`）に合わせたため、単体・結合テストと lint を実行した。

| 種別 | 結果 | ログ |
| --- | --- | --- |
| 単体 | 553 passed | [20261111055019_e03d233_単体テスト.log](./テスト結果/20261111055019_e03d233_%E5%8D%98%E4%BD%93%E3%83%86%E3%82%B9%E3%83%88.log) |
| 結合 | 181 passed | [20261111055019_e03d233_結合テスト.log](./テスト結果/20261111055019_e03d233_%E7%B5%90%E5%90%88%E3%83%86%E3%82%B9%E3%83%88.log) |
| lint | 違反なし | [20261111055019_e03d233_lint.log](./テスト結果/20261111055019_e03d233_lint.log) |
