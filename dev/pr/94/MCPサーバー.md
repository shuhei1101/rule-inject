# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/シナリオ/単一ユースケース/MCPサーバーを常駐させる.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC%E3%82%92%E5%B8%B8%E9%A7%90%E3%81%95%E3%81%9B%E3%82%8B.yaml) | 止めるシナリオの期待値「設定ファイルのポートで待ち受けていない」、ポートが使われているシナリオのセットアップ「テストが設定ファイルのポートを先に待ち受けておく」 | 更新対象 |
| ドキュメント | [設計書/モジュール構成/server/dev_docs.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/server/dev_docs.py.yaml) | 接続できないときの単体テストの条件「空いているポートを取ってすぐ閉じた `http://127.0.0.1:{ポート}/mcp`」 | 更新対象 |
| テスト | [tests/unit/rule_inject/server/test_dev_docs.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/unit/rule_inject/server/test_dev_docs.py) | `test_fetch_used_tags_when_unreachable` の bind してすぐ閉じるポート | 更新対象 |
| テスト | [tests/e2e/conftest.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/e2e/conftest.py) | `free_port`（待ち受けてすぐ閉じる）・`resident_server`（ポートへ接続できるかで起動を待つ）・`serve`・`start_dev_docs` | 更新対象 |
| テスト | [tests/e2e/単一ユースケース/test_run_resident_mcp_server.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/e2e/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/test_run_resident_mcp_server.py) | 4 テストとも `free_port` の番号で起動し、ポートの状態で確かめる | 更新対象 |
| テスト | [tests/e2e/単一ユースケース/test_check_indexes.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/e2e/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/test_check_indexes.py) | `test_error_when_dev_docs_unreachable` が `free_port` の番号を接続できない URL に使う | 更新対象 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| E2E のサーバー・偽の dev-docs の起動待ち | 子プロセスの標準エラーに `Uvicorn running on http://127.0.0.1:{ポート}` が出たことで起動を確かめる | 結合テストの `_wait_ready` と同じ確かめ方。偽の dev-docs の標準エラーも捨てずにファイルへ書く |
| E2E のサーバー・偽の dev-docs のポート | 待ち受けに失敗して子プロセスが終わったら、別の空いているポートで起動し直す | 起動を待つ上限と起動し直す回数は、テスト実行方法の結合テスト（バック）の補足で導いた値（`START_TIMEOUT_SEC` 51 秒・5 回）を使う |
| `test_error_when_port_in_use`（E2E） | テストがポート 0 で待ち受けて握ったポートを設定ファイルに書く | `free_port` の番号を後から待ち受けない |
| `test_normal_when_stopped`（E2E） | 停止後のポートへの接続の確かめに代えて、標準エラーの `Finished server process` で確かめる | シナリオの期待値も合わせる |
| `test_error_when_settings_unreadable`（E2E） | `ConnectionRefusedError` の確かめに代えて、標準エラーに `Uvicorn running on` が出ていないことで確かめる | |
| `test_normal`（E2E） | 起動を確かめたポートで `addresses_listening` を確かめる | 待ち受けの行で起動を確かめたポートは、サーバー自身が待ち受けている |
| 接続できない接続先（単体の `test_fetch_used_tags_when_unreachable`・E2E の `test_error_when_dev_docs_unreachable`） | テストが `SO_REUSEADDR` を付けずにポート 0 で bind し、listen しないまま握っている番号の URL を使う | 結合テストの `test_normal_when_dev_docs_unreachable` と同じ取り方 |

## テスト結果

### 単体

| ファイル | メソッド | 変更種別 | 結果 | 補足 |
| --- | --- | --- | --- | --- |
| [tests/unit/rule_inject/server/test_dev_docs.py](https://github.com/shuhei1101/rule-inject/blob/fix/server/dev-docs-url-and-test-ports/tests/unit/rule_inject/server/test_dev_docs.py) | 全実行 | 変更 | ✅ | `test_fetch_used_tags_when_unreachable` の接続先を変更<br>`テスト結果/20261101004114_b0705b7_単体テスト.log` |
| `tests/unit` の他のファイル | 全実行 | 実行のみ | ✅ | `tests/unit` 全体で 406 テスト pass<br>`テスト結果/20261101004114_b0705b7_単体テスト.log` |

### 結合

なし
