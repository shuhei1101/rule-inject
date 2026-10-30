# MCP サーバー

## 現状

<!-- table: data -->

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/シナリオ/単一ユースケース/索引をチェックする.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/%E7%B4%A2%E5%BC%95%E3%82%92%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF%E3%81%99%E3%82%8B.yaml) | 違反・ルールの場所にファイルが無いエントリ・読み飛ばすエントリ・`paths` の当たらないエントリを返すシナリオ | 使われていないタグのパターンの警告と、dev-docs に届かないときのシナリオを追加する |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/索引のチェック.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF.py.yaml) | `check_indexes` の入出力 | 応答に使われていないタグのパターンと、飛ばしたことを追加する |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/索引のチェック.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF.py.yaml) | 問題の種類と、プロジェクトのファイルを辿る関数 | 使われていないタグのパターンを確かめる関数と、問題の種類を追加する |
| ドキュメント | [設計書/モジュール構成/MCPサーバー/サーバー.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC.py.yaml) | ツールの本体と応答のモデル | `check_indexes` の応答のモデルを広げ、dev-docs へ問い合わせるクライアントを追加する |
| ドキュメント | `設計書/外部API/dev-docs.yaml`（新規） | - | dev-docs の `search_docs`（`group_by: tags`）の呼び出し方・接続先・エラーを書く |
| ドキュメント | [設計書/アーキテクチャ図/アーキテクチャ図.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A2%E3%83%BC%E3%82%AD%E3%83%86%E3%82%AF%E3%83%81%E3%83%A3%E5%9B%B3/%E3%82%A2%E3%83%BC%E3%82%AD%E3%83%86%E3%82%AF%E3%83%81%E3%83%A3%E5%9B%B3.yaml) | サブシステムと外部システム | 外部システム連携に dev-docs を追加する |
| ドキュメント | [設計書/設定/プラグイン.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E8%A8%AD%E5%AE%9A/%E3%83%97%E3%83%A9%E3%82%B0%E3%82%A4%E3%83%B3.yaml) | 設定ファイルのキー（接続は `server_port` だけ） | dev-docs の接続先のキーを追加する |
| ドキュメント | [設計書/非機能要件/非機能要件.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E9%9D%9E%E6%A9%9F%E8%83%BD%E8%A6%81%E4%BB%B6/%E9%9D%9E%E6%A9%9F%E8%83%BD%E8%A6%81%E4%BB%B6.yaml) | フックとサーバーの決定値 | dev-docs への問い合わせの待ち時間の上限を追加する |
| 実装 | [src/rule_inject/features/index/check/service.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/check/service.py)・[types.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/check/types.py) | `ProblemKind` は `hook_error`・`violation`・`missing_rule`・`skipped_entry`・`unmatched_path` | 使われていないタグのパターンの検出を、`check_change` を通らない別の関数として追加する |
| 実装 | [src/rule_inject/server/check_tools.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/check_tools.py)・[types.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/types.py) | `check_indexes` の本体と応答 | dev-docs から使われているタグを引き、応答に載せる |
| 実装 | [src/rule_inject/shared/_settings_yaml.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/shared/_settings_yaml.py)・[settings.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/shared/settings.py) | `global` のキーは `state_dir`・`log_dir`・保持日数・`server_port` | dev-docs の接続先のキーを追加する |
| 実装 | [tests/unit/rule_inject/server/test_check_tools.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/unit/rule_inject/server/test_check_tools.py)・[tests/integration/server/test_check_indexes.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/integration/server/test_check_indexes.py) | チェックのツールのテスト | dev-docs を Mock に差し替えたテストを追加する。`features/index/check/tags.py`・`server/dev_docs.py` の単体テストのファイルを作り、モジュール構成の `test_files` に追加する |

<!-- /table -->

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| タグのパターンの対象 | 効いているエントリの `args`（`read_by[].args` を含む）のうち、条件の木の `field: tags` の値に当てるパターンだけを確かめる | ドットの道筋で書いたキー（`filter.tags`）はタグとみなさない |
| 当たらないの判定 | dev-docs の `search_docs` を `group_by: tags`・`source: *` で 1 回の `check_indexes` につき 1 回だけ呼び、返ったタグのどれにも当たらないパターンを、索引・エントリの位置・バージョン・パターンつきで返す | 索引ごとに問い合わせ直さない |
| 届かないとき | 接続できない・待ち時間の上限を超えた・エラーを返したときは、この確かめだけを飛ばし、飛ばしたことと理由を応答に載せる。ツールのエラーにしない | ほかの問題の種類は今どおり返す |
| `problem_count` | 使われていないタグのパターンは数えない | dev-docs の文書の状態で増減する警告で、索引を読めなくする問題ではない |
| 書き込み前の検証 | `check_change` には含めない | 書く時点で、まだ文書に付けていないタグを指すことがあるため |
| 接続先 | dev-docs の接続先を設定ファイルのキーで持ち、既定は dev-docs の既定（`http://127.0.0.1:8781/mcp`） | dev-docs の `docs/リファレンス/文書のMCP.md` |

## テスト結果

未実施
