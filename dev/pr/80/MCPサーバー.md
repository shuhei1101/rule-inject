# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/非機能要件/非機能要件.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E9%9D%9E%E6%A9%9F%E8%83%BD%E8%A6%81%E4%BB%B6/%E9%9D%9E%E6%A9%9F%E8%83%BD%E8%A6%81%E4%BB%B6.yaml) | 「dev-docs への問い合わせの待ち時間」（108 秒、仮の p99.9 71.9 秒 + 36.0 秒） | 更新対象 |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/索引のチェック.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF.py.yaml) | 制約「問い合わせと辿る順」（待ち時間 108 秒、1 回の呼び出しの所要時間 162 秒） | 値が変わる場合に更新 |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/サーバー.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC.py.yaml) | 定数 `DEV_DOCS_TIMEOUT` の値（`108`） | 値が変わる場合に更新 |
| ドキュメント | [設計書/外部API/dev-docs.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E5%A4%96%E9%83%A8API/dev-docs.yaml) | `search_docs` の呼び出し方と、#77 での応答までの時間の実測 | 測る呼び出しの引数の出所。更新しない |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/app.py) | `DEV_DOCS_TIMEOUT = 108` | 値が変わる場合に更新 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 実測 | 手元で常駐している dev-docs（`http://127.0.0.1:8781/mcp/`）へ、`mcp` の `streamable_http_client` から外部 API「dev-docs」の引数で `search_docs` を 1 回ずつ順に呼ぶ。配信元ごと（51 件・589 件）に 1,000 回、接続から応答までの時間を測り、p99.9 を出す | 1 回 30〜70 秒かかるため、2 つの配信元で合わせて 1 日以上かかる。測るスクリプトと結果は `dev/pr/80/実測/` に置く |
| 待ち時間 | 2 つの配信元の p99.9 の大きい方 + その 50% を決定値にする。`breakdown` に配信元ごとの回数・p50・p99.9・最大と、余裕・決定値を並べる | 規約『資源の値の決め方』の「下流を待つタイムアウト」 |
| 1 回の呼び出しの所要時間の上限 | 待ち時間と辿る時間（30 秒）の大きい方 + 待ち時間の 50% で置き直す | 余裕の求め方は今のまま（`要件.md` の `## スコープ外`） |
| 定数 | `DEV_DOCS_TIMEOUT` を決定値にする | `build_server` の `dev_docs_timeout` の既定 |

## テスト結果

### 単体

| ファイル | メソッド | 変更種別 | 結果 | 補足 |
| --- | --- | --- | --- | --- |
| [tests/unit](https://github.com/shuhei1101/rule-inject/tree/develop/tests/unit) | 全実行 | 実行のみ | ✅ | 406 テスト pass<br>`テスト結果/20261031151452_c5dcf1e_単体テスト.log` |

### 結合

| ファイル | メソッド | 変更種別 | 結果 | 補足 |
| --- | --- | --- | --- | --- |
| [tests/integration](https://github.com/shuhei1101/rule-inject/tree/develop/tests/integration) | 全実行 | 実行のみ | ✅ | 140 テスト pass<br>`テスト結果/20261031151452_c5dcf1e_結合テスト.log` |
