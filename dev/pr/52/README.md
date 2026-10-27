# 利用者ごとの設定を環境変数から ~/.config/rule-inject/settings.yaml（global・projects）へ移す

## 概要

利用者が、rule-inject の設定（索引の場所・記録とログのフォルダ・保持日数）を `~/.config/rule-inject/settings.yaml` に記載し、プロジェクトごとの違いを `projects` で 1 か所にまとめて書けるようになる。

## 背景

[Issue #39](https://github.com/shuhei1101/rule-inject/issues/39) の要望。
rule-inject は利用者ごとの設定を環境変数 6 個（`RULE_INJECT_INDEXES_USER`・`RULE_INJECT_INDEXES_PROJECT`・`RULE_INJECT_STATE_DIR`・`RULE_INJECT_LOG_DIR`・`RULE_INJECT_RECORD_RETENTION_DAYS`・`RULE_INJECT_LOG_RETENTION_DAYS`）で直接受け取っている。
`env` はキーと値しか持てず、プロジェクトごとの違いを構造で書けない。
話し合いの D-87 で、`env` には設定ファイルのパスだけを書き、本体を `~/.config/{プラグイン}/` の YAML（`global`・`projects`）に書くと決め、knowledge の規約『claudeプラグイン』の `## 設定ファイル`（[shuhei1101/knowledge#58](https://github.com/shuhei1101/knowledge/issues/58)）に入った。
ファイル名とパスを渡す環境変数の名前は、[Issue のコメント](https://github.com/shuhei1101/rule-inject/issues/39#issuecomment-6383793360) で規約に合わせると決まった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と影響する UC 一覧 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [確認ログ](./確認ログ.md) | ユーザーへの確認事項の決着 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（現状設計書が揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（標準ライブラリだけで YAML を読む既存の方式の拡張で、未検証の技術機構に依存しない）
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
- [ ] E2E テスト作成
