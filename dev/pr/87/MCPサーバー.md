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
| サーバー・偽の dev-docs のポート | 起動した子プロセスが待ち受けに失敗して終わったら、別のポートで起動し直す | 回数の上限は `未確定` |
| 起動待ち | ポートへ接続できることに加え、子プロセス自身が待ち受けたことを確かめてから待ち受けたとみなす | 確かめ方は `未確定` |
| 設定ファイルのポートで待ち受けないことの確かめ（`test_normal_when_port_overridden`） | 他のプロセスがそのポートを取っても崩れない確かめ方にする | 確かめ方は `未確定` |
| 停止後・起動失敗後に待ち受けていないことの確かめ（`test_normal_when_stopped`・`test_error_when_settings_unreadable`） | 同上 | 確かめ方は `未確定` |
| 何も待ち受けていない接続先（`test_normal_when_dev_docs_unreachable`） | テストの間、他のプロセスがそのポートで待ち受けられない取り方にする | 取り方は `未確定` |

上の `未確定` は、インターフェース定義設計で決める。

| 案 | 内容 |
| --- | --- |
| A | 子プロセスの標準エラーに出る待ち受けの開始の行（uvicorn の `Uvicorn running on http://127.0.0.1:{ポート}`）で起動を確かめ、終わったら起動し直す。設定ファイルのポートで待ち受けないことは、テストがそのポートを待ち受けたまま起動して確かめる。何も待ち受けていない接続先は、テストが `listen` せずに `bind` したままのポートにする。停止後・起動失敗後は子プロセスの終了と標準エラーで確かめる |
| B | ポートを OS が自動で割り当てる範囲（`/proc/sys/net/ipv4/ip_local_port_range`）の外から選び、待ち受けの確かめは今のまま |

推奨: A

B は自動で割り当てるポートとの衝突は避けられるが、同じテストを同時に流す別のプロセスとの取り合いは残る。A は取り合いが起きても起動し直すか、他のプロセスが取れない状態で確かめるため、負荷や同時実行によらず崩れない。

## テスト結果

### 単体

なし

### 結合

なし
