# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/サーバーの起動.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC%E3%81%AE%E8%B5%B7%E5%8B%95.py.yaml) | 正常系・異常系のセットアップの「空いているポートを書いた設定ファイル」「設定ファイルと別の空いているポート」 | 取り方・確かめ方が変わる場合に更新 |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/索引のチェック.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF.py.yaml) | 正常系（dev-docsに届かない）のセットアップの「空いているポートを取ってすぐ閉じた番号を使う」と、偽の dev-docs の「空いているポートに立てた」 | 更新対象 |
| テスト | [tests/integration/server/conftest.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/integration/server/conftest.py) | `free_port`・`_start_shared`・`_wait_ready`・`start_fake_dev_docs` | 更新対象 |
| テスト | [tests/integration/server/test_server_start.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/integration/server/test_server_start.py) | `free_port` の番号で起動し、ポートへ接続できるかで確かめる | 更新対象 |
| テスト | [tests/integration/server/test_check_indexes.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/integration/server/test_check_indexes.py) | `test_normal_when_dev_docs_unreachable` が `free_port` の番号を接続できない URL に使う | 更新対象 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| サーバー・偽の dev-docs の起動待ち | 子プロセスの標準エラーに `Uvicorn running on http://127.0.0.1:{ポート}` が出たことで起動を確かめる | 偽の dev-docs の標準エラーも捨てずにファイルへ書く |
| サーバー・偽の dev-docs のポート | 待ち受けに失敗して子プロセスが終わったら、別の空いているポートで起動し直す（5 回まで） | `free_port`・`_start_shared`・`start_server`・`start_fake_dev_docs` |
| `test_normal_when_port_overridden` | 設定ファイルのポートは、テストがポート 0 で待ち受けて握ったまま起動し、起動に成功することで確かめる | `port_is_listening(config_port)` の確かめを外す |
| `test_error_when_port_in_use` | テストがポート 0 で待ち受けて握ったポートを設定ファイルに書く | `free_port` の番号を後から待ち受けない |
| `test_normal_when_stopped` | 停止後のポートへの接続の確かめに代えて、標準エラーの `Finished server process` で確かめる | |
| `test_error_when_settings_unreadable` | `ConnectionRefusedError` の確かめに代えて、標準エラーに `Uvicorn running on` が出ていないことで確かめる | |
| `test_normal_when_dev_docs_unreachable` | テストが `SO_REUSEADDR` を付けずにポート 0 で bind し、listen しないまま握っている番号の URL を使う | |

起動し直す回数の 5 回は、1 回の起動で取り合いが起きる確率 0.1・1 回の実行での起動 約 13 回から、1 回の実行が失敗する確率を 0.1% 以下にする回数として導いた（導き方はテスト実行方法の結合テスト（バック）の補足「起動し直す回数」）。

## テスト結果

### 単体

なし

### 結合

なし
