# dev-docs がタグを名前で返すようになった後の check_indexes のタグの判定を確かめる

## 概要

`tags` を `- name: ...` の要素で持つ配信元があっても、`check_indexes` が使われているタグのパターンを使われていないと報告しないようにする。

## 背景

[Issue #95](https://github.com/shuhei1101/rule-inject/issues/95) の要望。PR [#94](https://github.com/shuhei1101/rule-inject/pull/94) のレビューで見つかった。
dev-docs の `search_docs`（`group_by: tags`）が、knowledge の配信元のタグを `"{'name': 'topic:フロントエンド'}"` のように辞書を文字列にした値で返し、`src/rule_inject/server/dev_docs.py` の `_parse_tags` がその値をそのままタグにするため、`check_indexes` が使われている `topic:*`・`scope:*` のパターンを使われていないと報告する。
扱いの判断で、原因は dev-docs 側で修正し、rule-inject 側では吸収しないと決めた。依存の [shuhei1101/dev-docs#43](https://github.com/shuhei1101/dev-docs/issues/43)（[dev-docs#50](https://github.com/shuhei1101/dev-docs/pull/50)）と [shuhei1101/knowledge#139](https://github.com/shuhei1101/knowledge/issues/139)（[knowledge#140](https://github.com/shuhei1101/knowledge/pull/140)）が develop へ入った。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（現状設計書が揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（未検証の技術機構に依存しない）
- [x] ~~複合ユースケース設計~~（影響なし: シナリオの流れと期待値は変わらない）
- [x] ~~デザインスタイル選定~~（画面を持たない）
- [x] ~~画面一覧・画面遷移~~（画面を持たない）
- [x] ~~単一ユースケース設計~~（影響なし: 索引をチェックするシナリオは偽の dev-docs がタグの名前を返す前提で、変わらない）
- [x] ~~モック作成~~（画面を持たない）
- [x] ~~インターフェース定義設計~~（影響なし: `groups[].value` を使われているタグにする制約は変わらない）
- [x] ~~部品設計~~（画面を持たない）
- [x] ~~画面設計~~（画面を持たない）
- [ ] モジュール構成設計
- [ ] ドキュメント修正（要件.md の `## 更新ドキュメント`）
- [ ] 単体テスト作成
- [ ] 実装
- [ ] 結合テスト作成
- [x] ~~E2E テスト作成~~（E2E は偽の dev-docs を使い、応答の値は変わらない）
