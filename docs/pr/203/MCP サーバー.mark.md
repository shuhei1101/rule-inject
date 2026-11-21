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

## テスト結果

なし
