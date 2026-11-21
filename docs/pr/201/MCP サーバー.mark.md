# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/architecture/ARCH-122-1.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/architecture/ARCH-122-1.yaml) | サブシステムの分け方 | MCP サーバーの定義への参照を追加 |
| ドキュメント | [docs/interface/index.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/interface/index.yaml) | ツールごとのインターフェース定義（IF-122-1〜12） | MCP サーバーの定義の `tools[].interface` から指す |
| ドキュメント | [docs/scenario/SC-122-6.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/scenario/SC-122-6.yaml) | 接続時に作業の決まりを受け取る | 変更なし（回帰確認） |
| ドキュメント | [docs/module/MOD-122-37.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/module/MOD-122-37.py.yaml) | `app.py` のモジュール構成（ツールの登録と annotations・単体テストの期待） | annotations とテストの期待をインターフェース定義の `read_only`・`destructive` に合わせる |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/app.py) | サーバーの組み立てとツールの登録・instructions・description | 設計書に合わせて修正 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| MCP サーバーの定義 | `docs/mcp-server/` に `template-mcp-server` の設計書を 1 つ作成し、`server` を `rule-inject`、`connection` を `http`（`http://127.0.0.1:{RULE_INJECT_PORT}/mcp`）にする | `clients[]` は利用者の Claude Code が全てのツールを使用する 1 行。`inject` はフック `fill_config` が入れる引数 |
| ツールの一覧 | `tools[]` に `app.py` が登録する全てのツールを並べ、インターフェース定義を指す | インターフェース定義の `read_only`・`destructive` と `ToolAnnotations` を揃える |
| instructions・description | テンプレートの決まり（プロンプトファイル `mcp/rule-inject/instructions`・`mcp/rule-inject/tools/{ツール}`）と今の `app.py` の直書きを突き合わせ、設計書に合わせて置き場所と文面を直す | 置き場所はモジュール構成設計で確定する |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| インターフェース定義設計 | `747ac9e..61c5ab7` | ツールのインターフェース定義に `read_only`・`destructive` を記載した。`write_index_entry` は既存のエントリを書き換えるため `destructive: true` にし、実装の `destructiveHint` を設計書に合わせる |
| インターフェース定義設計 | `61c5ab7..c3acc4f` | レビューの指摘の修正。`restart_server` は削除・上書きするデータを持たないため `destructive: false` にした |
| エージェント・MCP サーバー設計 | `c3acc4f..3503545` | MCP サーバーの定義 MCP-122-1 を作成した（`c68d2e9` の反映作業で配信元の設定に種類の行を追加）。エージェントの定義・起動の構成は持たないため作成していない |

## テスト結果

なし
