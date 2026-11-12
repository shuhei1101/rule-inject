# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/architecture/ARCH-122-1.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/architecture/ARCH-122-1.yaml) | アーキテクチャ図 | サブシステム「MCP サーバー」と外部システム project-index が `planned` |
| ドキュメント | [docs/interface/IF-122-11.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/interface/IF-122-11.py.yaml) | 索引のチェック | 引数 `include_global`・`cursor` が `planned` |
| ドキュメント | [docs/library/LIB-122-3.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/library/LIB-122-3.yaml) | mcp | `streamable_http_client` が `planned` |
| ドキュメント | [docs/nonfunctional/NFR-122-1.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/nonfunctional/NFR-122-1.yaml) | 非機能要件 | NFR-7・NFR-9〜NFR-16 が `planned` |
| 実装 | [src/rule_inject/server/](https://github.com/shuhei1101/rule-inject/tree/develop/src/rule_inject/server)・[src/rule_inject/features/index/check/](https://github.com/shuhei1101/rule-inject/tree/develop/src/rule_inject/features/index/check) | 照合の相手 | 変更しない |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| ARCH-122-1 | サーバーの起動（`server/__main__.py`）と project-index への問い合わせ（`server/dev_docs.py`）があるため、2 行の `status` を外す | - |
| IF-122-11・LIB-122-3 | `check_indexes` の引数と `streamable_http_client` の呼び出しを実装で確かめ、ある行の `status` を外す | 無い行は `planned` のまま残し、行と理由をこの表に追記する |
| NFR-122-1 | 要件ごとに値を守る実装（待ち受けのアドレス・既定のポート・応答の字数・打ち切りの秒数 等）を確かめ、ある行の `status` を外す | 同上 |

## テスト結果

### 単体

なし

### 結合

なし
