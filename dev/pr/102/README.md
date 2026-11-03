# 索引のエントリごとに、ルールを参照する MCP のツールと引数を案内できるようにする

## 概要

索引の作成者が、エントリごとにルールを参照する MCP のツールと引数を記載でき、Claude Code はそのツールでルールの必要な部分だけを参照できるようになる。
ツールが使えないときは、これまでどおり Read で参照できる。

## 背景

[Issue #100](https://github.com/shuhei1101/rule-inject/issues/100) の要望。
案内文は「下の場所を Read で読んでください」に固定されている（`src/rule_inject/features/guidance/service.py` の `BLOCKING_HEADER`・`NON_BLOCKING_HEADER`・`SEARCH_HEADER`）。
索引の `read_by` で MCP のツールの呼び出しを既読にできるが、どのツールにどの引数を指定して参照するかを案内する機能は無い。
dev-docs の配信元の文書は `search_docs` に ID と `sections`・`fields` を指定すれば必要な部分だけを参照できるが、Read で YAML のファイル全体を読むと不要な部分もコンテキストに入る。
案内文を Read に固定したのは [#44](https://github.com/shuhei1101/rule-inject/pull/44)（rule-inject の MCP サーバーの `read_rules` の廃止）で、今回の変更は Read の案内を残したまま、他の MCP のツールでの参照を先に案内する。
この機能を使う側は [shuhei1101/knowledge#158](https://github.com/shuhei1101/knowledge/issues/158)（knowledge の文書を案内する索引の見直し）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（現状設計書が揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（未検証の技術機構に依存しない。案内文は既存のフックの `permissionDecisionReason`・`additionalContext` で返す）
- [x] 複合ユースケース設計
- [x] ~~デザインスタイル選定~~（画面を持たない）
- [x] ~~画面一覧・画面遷移~~（画面を持たない）
- [x] 単一ユースケース設計
- [x] ~~モック作成~~（画面を持たない）
- [x] インターフェース定義設計
- [x] ~~部品設計~~（画面を持たない）
- [x] ~~画面設計~~（画面を持たない）
- [x] モジュール構成設計
- [x] ドキュメント修正（要件.md の `## 更新ドキュメント`）
- [x] 単体テスト作成
- [x] 実装
- [x] 結合テスト作成
- [x] E2E テスト作成