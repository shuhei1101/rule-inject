# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/scenario/SC-122-12.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/scenario/SC-122-12.yaml) | 操作に該当するルールを検索する | 更新対象 |
| ドキュメント | [docs/scenario/SC-122-9.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/scenario/SC-122-9.yaml) | 有効なルールの一覧を確認する | 追随 |
| ドキュメント | [docs/scenario/SC-122-20.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/scenario/SC-122-20.yaml) | 索引をチェックする | 追随 |
| ドキュメント | [docs/interface/IF-122-8.py.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/interface/IF-122-8.py.yaml) | ルールの検索 | 更新対象。制約「照合」がフックと同じ索引を求めているが、設定ファイルはサーバーのプロセスの環境変数で決定する |
| ドキュメント | [docs/interface/IF-122-7.py.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/interface/IF-122-7.py.yaml) | ルールの一覧 | 更新対象（制約「読む索引」を検索・チェック・エントリ編集が参照する） |
| ドキュメント | [docs/interface/IF-122-11.py.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/interface/IF-122-11.py.yaml) | 索引のチェック | 追随 |
| ドキュメント | [docs/module/MOD-122-43.py.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/module/MOD-122-43.py.yaml) | MCP サーバー / サーバー / tools.py | 更新対象 |
| ドキュメント | [docs/module/MOD-122-37.py.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/module/MOD-122-37.py.yaml) | MCP サーバー / サーバー / app.py | ツールの引数を追加するとき更新する |
| 実装 | [src/rule_inject/server/tools.py](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/src/rule_inject/server/tools.py) | `_project_settings` がサーバーのプロセスの環境変数に `project_dir` を重ねて設定を取得する | 設定ファイルの場所の指定を受ける |
| 実装 | [src/rule_inject/server/check_tools.py](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/src/rule_inject/server/check_tools.py) | 索引のチェック。`_project_settings` を使用する | 同上 |
| ドキュメント | [docs/interface/IF-122-10.py.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/interface/IF-122-10.py.yaml) | 既読の記録の確認 | 更新対象。既読の記録の場所をサーバーの設定から取得する |
| ドキュメント | [docs/interface/IF-122-9.py.yaml](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/docs/interface/IF-122-9.py.yaml) | 既読の記録の削除 | 更新対象。同上 |
| 実装 | [src/rule_inject/server/record_tools.py](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/src/rule_inject/server/record_tools.py) | `_record_settings` が `_project_settings` とは別に `load_settings` を呼び、`PROJECT_DIR_ENV` を外して設定を取得する | 設定ファイルの場所の指定を受ける |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/src/rule_inject/server/app.py) | ツールの登録 | 引数を追加する |
| テスト | [tests/integration/server/test_search_rules.py](https://github.com/shuhei1101/rule-inject/blob/8a8d331781daf270ce8714186ed279696f71131c/tests/integration/server/test_search_rules.py) | ルールの検索の結合テスト | ケースを追加する |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 設定ファイルの決め方 | 検索・一覧・チェック・エントリ編集・既読の記録の確認と削除のツールは、呼んだセッションの設定ファイルの場所の指定があればそのファイル、無ければ今までどおりサーバーの環境変数（無ければ既定の場所）で設定を取得する | `未確定`（指定の方法は [要件](./要件.mark.md)） |
| 既読の記録のツールの設定の解決 | 設定ファイルの場所の選び方は `_project_settings` と同じ処理に寄せ、プロジェクトの直下を重ねないこと（記録の場所はプロジェクトに依らない）だけを既読の記録のツールの側で分ける | - |
| `config_path` | 照合に使用した設定ファイルの場所を返却する | - |
| 一致の確認 | 同じ設定・同じ対象・同じ操作で、`search_rules` の `matched` と `blocking` がルール案内の判定と一致することを結合テストで確認する | - |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| 単一ユースケース設計 | `707af58..2ba411b` | - |

## テスト結果

なし
