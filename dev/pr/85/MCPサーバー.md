# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/サーバー.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC.py.yaml) | 起動の入口・コンポジションルート・ツールの本体と応答の形式 | 8 つの物理ファイルの要素を持つ。分けて削除する |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/index.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/index.yaml) | MCP サーバーのモジュール構成の目次 | `サーバー.py.yaml` の行を削除する |
| ドキュメント | [src/files.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/src/files.yaml) | ソースコードの各ファイルと設計書との関連 | `rule_inject/server/` の 8 つの `related` を張り直す |
| 実装 | [src/rule_inject/server/](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server) | MCP サーバーの起動・ツール・応答のモデル | 変えない |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 設計書の分割 | 要素を `container` ごとに `モジュール構成/server/{物理ファイル}.yaml` の 8 つの設計書へ移す。書くツールの `create` で作る | - |
| 束ねる設計書 | `lead` と `directory` を、要素を持たない束ねる設計書 `モジュール構成/分類/MCPサーバー/サーバー.yaml` へ移す | - |
| 単体テストのファイル | `test_files` を物理ファイルごとに対応する設計書へ移す（`types.py` は単体テストのファイルを持たない） | - |
| 参照の張り直し | `src/files.yaml` の `related` の `to` と `index.yaml` の行を、分けた設計書へ置き換える | - |
| 既存機能への影響 | ソースコード・テスト・インターフェース定義は変えない | - |

## テスト結果

なし
