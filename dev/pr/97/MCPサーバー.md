# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/外部API/dev-docs.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E5%A4%96%E9%83%A8API/dev-docs.yaml) | `groups[].value` を「タグ（まとめた値の代表の表記）」とし、辞書を文字列にした値を返すことを書いていない。`verification` は 2026-10-30 | 更新対象 |
| ドキュメント | [設計書/モジュール構成/server/dev_docs.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/server/dev_docs.py.yaml) | `fetch_used_tags` の手順 7 が `groups[].value` の文字列を使われているタグにする | 変えない |
| 実装 | [src/rule_inject/server/dev_docs.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/dev_docs.py) | `_parse_tags` が `groups[].value` の文字列をそのままタグにする | 変えない |
| テスト | [tests/unit/rule_inject/server/test_dev_docs.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/unit/rule_inject/server/test_dev_docs.py) | `fetch_used_tags` の単体テスト | 変えない |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 確かめる前の準備 | 常駐している dev-docs を dev-docs の管理ツールで起動し直し、dev-docs の develop（9bac461 以降）のコードと knowledge の develop の `dev-docs.yaml`（eb35a25 以降）で応答させる | |
| dev-docs の応答の確認 | `search_docs` を `check_indexes` と同じ引数（`source: "*"`・`group_by: "tags"`・`format: "json"`・`cwd`: rule-inject のクローン）で呼び、`groups[].value` のうち `{` で始まる値の件数を数える | 0 件で合格 |
| `check_indexes` の確認 | 同じ dev-docs を接続先にして `check_indexes` を呼び、knowledge の配信元で使われている `topic:*`・`scope:*` のタグに当たるパターンが使われていないと報告されないことを確かめる | |
| 外部 API『dev-docs』 | `groups[].value` の補足と `verification` を確かめた結果に合わせる | |
| `_parse_tags` | 変えない | 2026-11-01 の確認で `{'name': ...}` の値が 0 件だったため |

### 確かめた結果（2026-11-01）

設計の段で planner が確かめた。外部 API『dev-docs』の `verification` はこの結果で書く。

| 確認 | 手順 | 結果 |
| --- | --- | --- |
| 準備 | 常駐の dev-docs（`http://127.0.0.1:8781/mcp`、2026-10-31 10:25 JST 起動）を dev-docs の管理ツールの `restart` で起動し直した。dev-docs の develop は d358fe3（dev-docs#50 の 9bac461 を含む）、knowledge の develop は eb35a25 | 起動し直す前は `groups` 958 件のうち 915 件が `{'name': ...}` の値だった |
| dev-docs の応答 | rule-inject の `fetch_used_tags`（`check_indexes` と同じ引数。`cwd`: `/mnt/c/Users/shuhe/repo/rule-inject`）を呼んだ | タグ 800 件、`{` で始まる値 0 件、`topic:` で始まる値 527 件・`scope:` で始まる値 19 件。約 35 秒で返った |
| `check_indexes` | `filter[tags]` に `topic:フロントエンド`・`scope:next`・`re:^topic:`・`re:^scope:`・`topic:存在しないタグ` を持つ一時の索引を `RULE_INJECT_CONFIG` の `global.indexes` に置き、`check_tools.check_indexes` を `project_dir`: rule-inject のクローンで呼んだ | `tag_check.state` が `checked`、`unused_tag_patterns` は `topic:存在しないタグ` の 1 件だけ |

## テスト結果
