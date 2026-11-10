# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/interface/IF-122-6.py.yaml](https://github.com/shuhei1101/rule-inject/blob/69931c3680dbb277c7532e99cdd0cbf7256a0d68/docs/interface/IF-122-6.py.yaml) | サーバーの起動。`initialize` の応答を定める | 応答の `instructions` を追加 |
| ドキュメント | [docs/module/MOD-122-37.py.yaml](https://github.com/shuhei1101/rule-inject/blob/69931c3680dbb277c7532e99cdd0cbf7256a0d68/docs/module/MOD-122-37.py.yaml) | サーバーの組み立て（`build_server`）。`MCPServer(SERVER_NAME)` を作る | instructions の定数と、`MCPServer` への指定を追加 |
| ドキュメント | [docs/library/LIB-122-3.yaml](https://github.com/shuhei1101/rule-inject/blob/69931c3680dbb277c7532e99cdd0cbf7256a0d68/docs/library/LIB-122-3.yaml) | mcp。`MCPServer` の使用する API | `MCPServer` の `instructions` の引数を追加 |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/69931c3680dbb277c7532e99cdd0cbf7256a0d68/src/rule_inject/server/app.py) | `MCPServer(SERVER_NAME)` に instructions を指定していない | instructions を指定 |
| テスト | [tests/unit/rule_inject/server/test_app.py](https://github.com/shuhei1101/rule-inject/blob/69931c3680dbb277c7532e99cdd0cbf7256a0d68/tests/unit/rule_inject/server/test_app.py) | `build_server` の単体テスト | instructions の確認を追加 |
| テスト | [tests/integration/server/test_server_start.py](https://github.com/shuhei1101/rule-inject/blob/69931c3680dbb277c7532e99cdd0cbf7256a0d68/tests/integration/server/test_server_start.py) | 子プロセスのサーバーへ MCP のクライアントで接続する結合テスト | `initialize` の応答の `instructions` の確認を追加 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| instructions の文面 | 新しいファイルは Write で空の内容で作り、案内されたルールを参照してから Edit で中身を記載する決まりを、事実の文で記載する。4,096 字以内 | 今の `WORK_RULES` の文面を元にする。ツールの使い分けを含めるかはスコープ外の行のとおりインターフェース定義のレビューで確定する |
| instructions の置き場所 | `server/app.py` の定数にし、`build_server` が `MCPServer(SERVER_NAME, instructions=...)` に指定する | 設定ファイルでは変えられない |
| `initialize` の応答 | `instructions` に上の文面が入る | 接続のたびに同じ文面 |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| インターフェース定義設計 | `e5c6aac..821948d` | IF-122-6 |

## テスト結果

なし
