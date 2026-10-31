# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/エントリの編集.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%A8%E3%83%B3%E3%83%88%E3%83%AA%E3%81%AE%E7%B7%A8%E9%9B%86.py.yaml) | 索引のエントリの round-trip での書き込み・削除 | `features/index/edit/` の 3 つの物理ファイルの要素を持つ。関数型の `summary` が `MCPサーバー/索引のチェック.py` を指す。分けて削除する |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/索引のチェック.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF.py.yaml) | 索引のフックの読み取り・JSON Schema・ルールの場所の実在のチェック | `features/index/check/` の 4 つの物理ファイルの要素を持つ。分けて削除する |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/index.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/index.yaml) | MCP サーバーのモジュール構成の目次 | 2 つの設計書を分けると空になるため、フォルダごと削除する |
| ドキュメント | [設計書/モジュール構成/分類/MCPサーバー/index.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/%E5%88%86%E9%A1%9E/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/index.yaml) | MCP サーバーの束ねる設計書の目次 | 2 つの行を追加する |
| ドキュメント | [src/files.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/src/files.yaml) | ソースコードの各ファイルと設計書との関連 | `rule_inject/features/index/edit/`・`check/` の `related` を張り直す |
| 実装 | [src/rule_inject/features/index/](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index) | 索引のチェックとエントリの編集のサブフィーチャー | 変えない |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 設計書の分割 | 要素を `container` ごとに `モジュール構成/features/index/edit/{types,_yaml,service}.py.yaml` と `モジュール構成/features/index/check/{types,service,scan,tags}.py.yaml` の設計書へ移す。書くツールの `create` で作る | - |
| 束ねる設計書 | `lead`・`directory`・`notes` を、要素を持たない束ねる設計書 `モジュール構成/分類/MCPサーバー/{エントリの編集,索引のチェック}.yaml` へ移す | - |
| 単体テストのファイル | `test_files` を物理ファイルごとに対応する設計書へ移す | `check/types.py` は単体テストのファイルを持たない |
| 参照の張り直し | `src/files.yaml` の `related` の `to` を分けた設計書へ置き換える（`check/index.schema.yaml` は JSON Schema の決まりを持つ束ねる設計書 `分類/MCPサーバー/索引のチェック`）。エントリの編集の関数型の `summary` が指す `MCPサーバー/索引のチェック.py` を `features/index/check/service.py` の設計書へ置き換える | - |
| 目次 | `モジュール構成/MCPサーバー/` を削除し、`モジュール構成/index.yaml` から行を削除する | - |
| 既存機能への影響 | ソースコード・テスト・インターフェース定義は変えない | - |

## テスト結果

なし
