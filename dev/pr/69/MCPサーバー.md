# MCP サーバー

## 現状

<!-- table: data -->

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/シナリオ/単一ユースケース/索引をチェックする.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/%E7%B4%A2%E5%BC%95%E3%82%92%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF%E3%81%99%E3%82%8B.yaml) | 違反・ルールの場所にファイルが無いエントリ・読み飛ばすエントリを返すシナリオ | `paths` の当たらないエントリを返すシナリオを追加する |
| ドキュメント | `設計書/シナリオ/単一ユースケース/` の既読の記録の確認・削除（新規） | - | 2 つのツールのシナリオを追加する |
| ドキュメント | `設計書/シナリオ/複合ユースケース/既読の記録を削除して案内を受け直す.yaml`（新規） | - | 確認 → 削除 → フックの案内が戻る流れを追加する |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/索引のチェック.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF.py.yaml) | `check_indexes` の入出力 | 応答に `paths` の当たらないエントリの一覧と、辿るのをやめたことを追加する |
| ドキュメント | `設計書/インターフェース定義/MCPサーバー/` の既読の記録の確認・削除（新規） | - | 2 つのツールを追加する |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/索引のチェック.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF.py.yaml) | `ProblemKind` は `hook_error`・`violation`・`missing_rule`・`skipped_entry` | 問題の種類と、プロジェクトのファイルを辿る関数を追加する |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/サーバー.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC.py.yaml) | 5 つのツールの本体と応答のモデル | 2 つのツールと応答のモデルを追加し、`IndexReport` に一覧を追加する |
| ドキュメント | [設計書/非機能要件/非機能要件.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E9%9D%9E%E6%A9%9F%E8%83%BD%E8%A6%81%E4%BB%B6/%E9%9D%9E%E6%A9%9F%E8%83%BD%E8%A6%81%E4%BB%B6.yaml) | フックとサーバーの決定値 | 辿るファイルの数の上限を追加する |
| 実装 | [src/rule_inject/features/index/check/service.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/check/service.py)・[types.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/check/types.py) | `check_index_text` が書く前と書いた後の比較（`check_change`）にも使われる | `paths` の当たらないエントリの検出を、`check_change` を通らない別の関数として追加する |
| 実装 | [src/rule_inject/server/tools.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/tools.py)・[types.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/types.py)・[app.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/app.py) | ツールは `list_rules`・`search_rules`・`check_indexes`・`write_index_entry`・`delete_index_entry` | 2 つのツールを追加し、`check_indexes` の応答を広げる |
| 実装 | [src/rule_inject/shared/settings.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/shared/settings.py) | `Settings.indexes` は `global.indexes`（無ければユーザーの既定の索引）とプロジェクトの索引を 1 つの並びで持つ | プロジェクトの索引を分けて引けるようにする |
| 実装 | [tests/unit/rule_inject/features/index/check/test_service.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/unit/rule_inject/features/index/check/test_service.py)・[tests/unit/rule_inject/server/test_tools.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/unit/rule_inject/server/test_tools.py)・[tests/integration/server/test_check_indexes.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/integration/server/test_check_indexes.py) | チェックとツールのテスト | テストを追加・変更する。2 つのツールの結合テストと E2E テストを新規に作る |

<!-- /table -->

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 検出の範囲 | 効いているエントリのうち `paths` を持つものを、`project_dir` の下のファイルの絶対パスに `paths` と `exclude` で当て、どれにも当たらないものを返す | 辿る範囲と上限は `要件.md` の `未確定` |
| 書き込み前の検証 | `check_change` には `paths` の当たらないエントリを含めない | 書く時点で対象のファイルがまだ無いことがあるため |
| 辿る回数 | 1 回の `check_indexes` でプロジェクトのファイルを 1 回だけ辿り、全ての索引のエントリをその結果に当てる | 索引ごとに辿り直さない |
| セッションと記録フォルダ | 既読の記録のツールは `project_dir` を受けず、`CLAUDE_PROJECT_DIR` 無しで設定を読み（`load_settings`）、その `state_dir` の記録を扱う。`session_id` はフックと同じ形式（`is_valid_session_id`）だけを受ける | 記録フォルダは `global.state_dir` だけで決まり、記録のファイルはプロジェクトを持たないため。形式に合わない値はファイルのパスにしない |
| 確かめる索引 | `paths` の当たらないエントリは、既定では当たった `projects[].indexes` とプロジェクトの既定の置き場所の索引のエントリだけを確かめる。引数でオンにしたときだけユーザー全体の索引も確かめ、分けて返す | `Settings.indexes` は索引の出所を持たないため、プロジェクトの索引を分けて引けるようにする |
| 削除 | 既読の記録の削除は、フックの圧縮の前の削除と同じ関数（`delete_record` ほか）を使う | 既読の記録と案内済みの記録をファイルごと削除する（`要件.md` の `## 要望`） |

## テスト結果

なし
