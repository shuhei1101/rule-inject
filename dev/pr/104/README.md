# リポジトリの直下にルール索引 rules.yaml を追加し、このプロジェクトの規約を案内する

## 概要

このリポジトリで作業する Claude Code が、ファイルを書く・ツールを呼ぶ前に、プロジェクト固有の規約・テンプレートと、使っているスタックの knowledge の規約の案内を受けられるようになる。

## 背景

[Issue #101](https://github.com/shuhei1101/rule-inject/issues/101) の要望。
環境変数 `RULE_INJECT_INDEXES_PROJECT` は直下の `rules.yaml` と `docs/rules.yaml` を指すが、直下の `rules.yaml` は無く、`docs/rules.yaml` は `rules: []` だけ。
索引の読み込みが失敗し続け（`~/.local/state/rule-inject/logs/20261103_rule-inject.log` の `read_index` で、11-03 だけで 112 回 `FileNotFoundError`）、このプロジェクトのルールは 1 件も案内されない。
索引を指す設定が実在しないファイルを指す事象は [#62](https://github.com/shuhei1101/rule-inject/issues/62) で扱い、[shuhei1101/ai-monitor#3040](https://github.com/shuhei1101/ai-monitor/issues/3040) へ集約済み。
knowledge 側の索引の見直しは [shuhei1101/knowledge#158](https://github.com/shuhei1101/knowledge/issues/158) が扱う。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [反映作業](./反映作業/index.yaml) | master へ入った後の索引の読み込みの確認 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（現状設計書が揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（未検証の技術機構に依存しない。索引の書式は既存のもの）
- [x] ~~複合ユースケース設計~~（影響なし: rule-inject の機能を変えない）
- [x] ~~デザインスタイル選定~~（画面を持たない）
- [x] ~~画面一覧・画面遷移~~（画面を持たない）
- [x] ~~単一ユースケース設計~~（影響なし: rule-inject の機能を変えない）
- [x] ~~モック作成~~（画面を持たない）
- [x] ~~インターフェース定義設計~~（影響なし: フック・MCP のツールの入出力を変えない）
- [x] ~~部品設計~~（画面を持たない）
- [x] ~~画面設計~~（画面を持たない）
- [x] ~~モジュール構成設計~~（影響なし: コードを変えない）
- [ ] ドキュメント修正（要件.md の `## 更新ドキュメント`）
- [x] ~~単体テスト作成~~（コードを変えない）
- [ ] 実装（直下の `rules.yaml` の作成と、`check_indexes` での検査）
- [x] ~~結合テスト作成~~（コードを変えない）
- [x] ~~E2E テスト作成~~（シナリオを変えない）
