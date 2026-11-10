# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/interface/IF-122-3.py.yaml](https://github.com/shuhei1101/rule-inject/blob/163a05f/docs/interface/IF-122-3.py.yaml) | インターフェース定義『サーバーの再起動』 | 制約「再起動の途中の呼び出し」「停止の待ち」「待ち受けの閉じ方」を修正する |
| ドキュメント | [docs/interface/IF-122-4.py.yaml](https://github.com/shuhei1101/rule-inject/blob/163a05f/docs/interface/IF-122-4.py.yaml) | インターフェース定義『サーバーの更新』 | 制約「再起動」が『サーバーの再起動』を指すため追随だけ |
| ドキュメント | `docs/library/LIB-122-6.yaml` | 外部ライブラリ『sse-starlette』 | 新規。停止を検知すると送信中の SSE の応答を取り消す挙動の動作確認を記録する |
| ドキュメント | [docs/module/MOD-122-40.py.yaml](https://github.com/shuhei1101/rule-inject/blob/163a05f/docs/module/MOD-122-40.py.yaml) | モジュール構成『control.py』 | 処理中の数え方・停止の待ち・単体テストの行を修正する |
| ドキュメント | [docs/module/MOD-122-34.py.yaml](https://github.com/shuhei1101/rule-inject/blob/163a05f/docs/module/MOD-122-34.py.yaml) | モジュール構成『__main__.py』 | 応答の送信の終わりを数える箇所を起動の入口に配置する場合に修正する |
| 実装 | [src/rule_inject/server/control.py](https://github.com/shuhei1101/rule-inject/blob/163a05f/src/rule_inject/server/control.py) | 処理中の呼び出しの数と停止の待ち | `_in_flight` は `guard` の `finally` で減る |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/163a05f/src/rule_inject/server/app.py) | ツールの登録 | `restart_server`・`get_server_status` は `guard` で包まない |
| 実装 | [src/rule_inject/server/__main__.py](https://github.com/shuhei1101/rule-inject/blob/163a05f/src/rule_inject/server/__main__.py) | 起動の入口 | `uvicorn.Server` に Streamable HTTP の ASGI アプリを指定する |
| テスト | [tests/unit/rule_inject/server/test_control.py](https://github.com/shuhei1101/rule-inject/blob/163a05f/tests/unit/rule_inject/server/test_control.py) | 停止の待ちの単体テスト | 数え方を変えるため修正する |
| テスト | [tests/integration/server/test_update_server.py](https://github.com/shuhei1101/rule-inject/blob/163a05f/tests/integration/server/test_update_server.py) | 『サーバーの更新』の結合テスト | `test_normal` が事象を再現する |
| テスト | [tests/integration/server/test_restart_server.py](https://github.com/shuhei1101/rule-inject/blob/163a05f/tests/integration/server/test_restart_server.py) | 『サーバーの再起動』の結合テスト | 同じ停止の待ちを通る |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 処理中の数え方 | `/mcp` への POST の要求を受けてから、応答の本文を送信し終える（ASGI の送信の最後の `http.response.body`）か接続が切れるまでを処理中として数える | `GET /mcp` の SSE のストリームは数えない。数える箇所（ASGI の層・`ServerControl`）はモジュール構成設計で決める |
| 停止の待ち | `_drain_and_stop` は上の数が 0 になるまで `STOP_DRAIN_TIMEOUT` を上限に待つ | 停止を始めた呼び出し自身の要求も、応答を送信し終えるまで数に入る |
| 再起動の途中の断り | `guard` の断り方（`RestartInProgressError`）は変えない | 断った呼び出しもエラーの応答を送信し終えるまで数える |
| インターフェース定義 | 『サーバーの再起動』の「待ち受けの閉じ方」の `notes` を、閉じた後に残るのは SSE のストリームと停止の待ちを過ぎた呼び出しだけ、と修正する | 『サーバーの更新』は参照だけのため変えない |
| 単体テスト | 応答を送信し終えるまで `should_exit` が立たないことを確認するテストを追加・修正する | - |
| 結合テスト | 変更しない | 事象が起きないことをファイル単体の繰り返しの実行で確認する |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| インターフェース定義設計 | `63fbd7e..e11cac6` | - |

## テスト結果

なし
