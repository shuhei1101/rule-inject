# plugin.json の版を version.ini・pyproject.toml と揃え、版上げで 3 つとも更新されるようにする

## 概要

`.claude-plugin/plugin.json` の版を `version.ini`・`pyproject.toml` と揃え、release の版上げで 3 つとも更新されるようにする。

## 背景

[Issue #24](https://github.com/shuhei1101/rule-inject/issues/24) の報告。
`version.ini` が `v0.1.1`、`pyproject.toml` が `0.1.1` なのに対し、`.claude-plugin/plugin.json` は `0.1.0` のまま。
v0.1.1 の版上げ（[ff2e2d3](https://github.com/shuhei1101/rule-inject/commit/ff2e2d32ba34e328af3c1377f17a9488f9461ee3)）が `plugin.json` を更新していない。
`plugin.json` の `version` が変わらない間、marketplace から入れた利用者には新しい版が届かない（[task-reviewer の指摘](https://github.com/shuhei1101/rule-inject/issues/24#issuecomment-6134976675)）。
作業 PR [#23](https://github.com/shuhei1101/rule-inject/pull/23) のレビューで対象外の逸脱として [報告](https://github.com/shuhei1101/rule-inject/pull/23#discussion_r4250640684) された。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（現状設計書が揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（未検証の技術機構に依存しない）
- [x] ~~複合ユースケース設計~~（影響なし: シナリオは変わらない）
- [x] ~~デザインスタイル選定~~（利用者に見える画面を持たない）
- [x] ~~画面一覧・画面遷移~~（利用者に見える画面を持たない）
- [x] ~~単一ユースケース設計~~（影響なし: シナリオは変わらない）
- [x] ~~モック作成~~（利用者に見える画面を持たない）
- [x] ~~インターフェース定義設計~~（影響なし: フックと MCP のツールの入出力は変わらない）
- [x] ~~部品設計~~（画面を持たない）
- [x] ~~画面設計~~（変更が画面に及ばない）
- [x] ~~モジュール構成設計~~（影響なし: クラス・関数は変わらない）
- [x] ドキュメント修正（設計書/非機能要件/非機能要件.yaml・設計書/テスト/テスト実行方法.yaml）
- [ ] 単体テスト作成（非機能要件テスト tests/nfr/test_version_consistency.py）
- [ ] 実装
- [x] ~~結合テスト作成~~（インターフェース定義は変わらない）
- [x] ~~E2E テスト作成~~（シナリオは変わらない）
