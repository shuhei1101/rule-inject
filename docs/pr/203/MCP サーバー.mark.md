# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/mcp-server/MCP-122-1.yaml](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/docs/mcp-server/MCP-122-1.yaml) | rule-inject の MCP サーバーの定義 | プロンプトファイルの id はテンプレートの決まりで導くため記載しない |
| ドキュメント | [docs/interface/IF-122-6.py.yaml](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/docs/interface/IF-122-6.py.yaml) | サーバーの起動 | 制約「instructions」が文面を持つ。文面の原本をプロンプトファイルへ移す |
| ドキュメント | [docs/module/MOD-122-37.py.yaml](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/docs/module/MOD-122-37.py.yaml) | サーバーのコンポジションルート | 定数 `SERVER_INSTRUCTIONS` と単体テスト `test_build_server_instructions` が更新の対象 |
| ドキュメント | [docs/module/MOD-122-53.yaml](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/docs/module/MOD-122-53.yaml) | MCP サーバーの構成 | プロンプトファイルの読み込みの配置先が無い |
| ドキュメント | [docs/layout/LAY-173-1.yaml](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/docs/layout/LAY-173-1.yaml) | フォルダ構成 | `content/prompts/` が無い |
| ドキュメント | [docs/scenario/SC-122-6.yaml](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/docs/scenario/SC-122-6.yaml) | MCP サーバーへの接続時に作業の決まりを受け取る | 振る舞いは変わらない |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/src/rule_inject/server/app.py) | サーバーのコンポジションルート | `SERVER_INSTRUCTIONS` とツール関数の docstring に本文を直接記載 |
| 設定 | [project-index.yaml](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/project-index.yaml) | 配信元の設定 | プロンプトの文書の行が無い |
| 設定 | [pyproject.toml](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/pyproject.toml) | 依存 | MCP サーバーの依存に jinja2 が無い |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| プロンプトファイル | `content/prompts/mcp/rule-inject/instructions.yaml` と、ツールごとの `content/prompts/mcp/rule-inject/tools/{ツール}.yaml` を作り、今の文面を `lang: ja` の部品 1 つへ移す | ファイル名の `_` は `-` にする |
| 読み込み | プロンプトファイルを id で読み込み、`lang` の本文を描画して返却する関数を MCP サーバーに配置する。プロンプトファイルの場所はクローンの直下（`find_clone`）から導く | 本文の描画の仕方は `要件.mark.md` の `未確定` |
| サーバーの組み立て | `build_server` が instructions とツールの description をプロンプトファイルから読み込み、`MCPServer` と `add_tool` の `description` に指定する。`SERVER_INSTRUCTIONS` とツール関数の docstring の本文を削除する | - |
| 異常 | プロンプトファイルが無い・読めない・スキーマに合わないときは、サーバーの組み立てを例外で止める | 起動の失敗として扱う |
| 既存機能への影響 | クライアントが受け取る instructions と description の文面は変えない | 単体テストで移す前の文面と比べる |
| 依存 | 本文の描画に jinja2 を使用する場合、`pyproject.toml` の `server` と `dev` に追加し、外部ライブラリの設計書を追加する | - |
| 配信元の設定 | `project-index.yaml` に `content/prompts/**/*.yaml` を指すプロンプトの文書の行を追加する | スキーマは knowledge の `schemas/prompt.schema.yaml` |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| インターフェース定義設計 | `85706a2..9624909` | - |
| インターフェース定義設計 | `3a2200d..1f0b5e8` | レビューの指摘の修正 |
| エージェント・MCP サーバー設計 | `62f3006..bc4cbc1` | プロンプトファイル 12 枚。MCP-122-1 はテンプレートの決まりでプロンプトファイルの id を記載しないため変更なし |
| モジュール構成設計 | `7038f45..44fbc24` | ライブラリ選定（jinja2）の設計書は `c1982cc..35cb413` |
| モジュール構成設計 | `ff020f8..eb483d0` | レビューの提案の反映（部品と `texts[]` の要素の構造の確認）。IF-122-6 の例外の条件も合わせた |

## テスト結果

### 単体

| ファイル | メソッド | 変更種別 | 結果 | 補足 |
| --- | --- | --- | --- | --- |
| `tests/unit/rule_inject/server/test_prompts.py` | 全実行 | 新規 | ✅ | 8 テスト pass<br>`テスト結果/20261121204741_5b03bff_単体テスト.log` |
| [tests/unit/rule_inject/server/test_app.py](https://github.com/shuhei1101/rule-inject/blob/f8c3c12/tests/unit/rule_inject/server/test_app.py) | 全実行 | 変更 | ✅ | `test_build_server_descriptions`・`test_build_server_when_prompt_missing` を追加、`test_build_server_instructions` を変更<br>`テスト結果/20261121204741_5b03bff_単体テスト.log` |
| [tests/unit/rule_inject/server/test_main.py](https://github.com/shuhei1101/rule-inject/blob/f8c3c12/tests/unit/rule_inject/server/test_main.py) | 全実行 | 変更 | ✅ | `test_main_when_prompt_unreadable` を追加<br>`テスト結果/20261121204741_5b03bff_単体テスト.log` |
| `tests/unit` のほかのファイル | 全実行 | 実行のみ | ✅ | 単体テスト全件 597 pass<br>`テスト結果/20261121204741_5b03bff_単体テスト.log` |

### 結合テストの実行範囲

`judge_integration_scope` は全ての行を R7（要調査）にしたため、変更したファイルを参照する結合テストを調べて記載した。

| 変更したファイル | 結果 | 実行する結合テスト | 結合テストが無いエントリーポイント |
| --- | --- | --- | --- |
| `content/prompts/mcp/rule-inject/instructions.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/check-indexes.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/delete-index-entry.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/delete-read-records.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/get-read-records.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/get-server-status.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/list-rules.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/reload-settings.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/restart-server.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/search-rules.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/update-server.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `content/prompts/mcp/rule-inject/tools/write-index-entry.yaml` | R7 | `tests/integration/server/test_server_start.py` | - |
| `docs/interface/IF-122-6.py.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/layout/LAY-173-1.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/library/LIB-122-4.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/library/LIB-203-1.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/library/index.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/module/MOD-122-34.py.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/module/MOD-122-37.py.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/module/MOD-203-1.py.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/module/index.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/MCP サーバー.mark.md` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/README.mark.md` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/タスク一覧.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/テスト結果/20261121203940_f8c3c12_単体テスト.log` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/テスト結果/20261121203639_3076c7a_単体テスト.log` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/テスト結果/20261121204741_5b03bff_単体テスト.log` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/テスト結果/20261121204244_f8c3c12_lint.log` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/テスト結果/20261121204741_5b03bff_lint.log` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/テスト結果/20261121204741_5b03bff_単体テスト.log` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/要件.mark.md` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `docs/pr/203/要件.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `project-index.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `pyproject.toml` | R7 | `tests/integration/server/test_server_start.py`・`tests/integration/server/test_update_server.py` | - |
| `src/files.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `src/rule_inject/server/__main__.py` | R7 | `tests/integration/server/test_server_start.py` | - |
| `src/rule_inject/server/app.py` | R7 | `tests/integration/server/test_server_start.py`・`tests/integration/server/test_update_server.py` | - |
| `src/rule_inject/server/prompts.py` | R7 | `tests/integration/server/test_server_start.py`・`tests/integration/server/test_update_server.py` | - |
| `tests/files.yaml` | R7 | -（設計書・PR ドキュメント・配信元の設定・管理用の YAML で、サーバーの動きに影響しない） | - |
| `tests/unit/rule_inject/server/test_app.py` | R7 | -（単体テストで、結合テストに影響しない） | - |
| `tests/unit/rule_inject/server/test_main.py` | R7 | -（単体テストで、結合テストに影響しない） | - |
| `tests/unit/rule_inject/server/test_prompts.py` | R7 | -（単体テストで、結合テストに影響しない） | - |
| `uv.lock` | R7 | `tests/integration/server/test_server_start.py`・`tests/integration/server/test_update_server.py` | - |

`test_update_server.py` は `start_clone_server` で作業ブランチの HEAD の一時のクローンから起動するため、クローンの `content/prompts` を読む経路を確かめる。ほかのツールの結合テストもサーバーを起動するが、起動の経路は `test_server_start.py` と同じで、各ツールの振る舞いは変えていないため含めない。
