# rule-inject の既存の文書全体を dev-docs.yaml に載せ、タグで引けるようにする

## 概要

dev-docs で文書を検索する人が、rule-inject の設計書・利用者向けのページ・ソースコード・テストを、タグ・説明・関連で引けるようになる。

## 背景

[Issue #70](https://github.com/shuhei1101/rule-inject/issues/70) の要望。
[#72](https://github.com/shuhei1101/rule-inject/pull/72)（[Issue #67](https://github.com/shuhei1101/rule-inject/issues/67)）で `dev-docs.yaml` を置いたが、載せたのは判定フローチャートの 1 ページだけで、残りの文書は dev-docs で配信されていない。
その後、dev-docs の設定のバージョンが 3 になり（[shuhei1101/dev-docs#32](https://github.com/shuhei1101/dev-docs/issues/32)・[shuhei1101/dev-docs#34](https://github.com/shuhei1101/dev-docs/issues/34)）、行の `type`・`custom` が無くなって、Markdown・ソースコードは管理用の YAML（`files.yaml`）に載せる形になった。
develop の `dev-docs.yaml` はバージョン 1 のままで、利用者の端末の dev-docs では配信から外されている（[コメント](https://github.com/shuhei1101/rule-inject/issues/70#issuecomment-6517091151)）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理・影響するユースケース・更新ドキュメント・スコープ外 |
| [反映作業](./反映作業/index.yaml) | マージの後に dev-docs で配信されたことを確かめる作業 |

## タスク一覧

- [x] ~~初期構築~~（既存リポジトリのため対象外）
- [x] ~~リバースエンジニアリング~~（現状設計書が揃っている）
- [x] ~~方針決め~~（方針決めを依頼する Issue ではない）
- [x] ~~PoC 検証~~（未検証の技術機構に依存しない）
- [x] ~~複合ユースケース設計~~（影響なし: 配信の設定の変更だけ）
- [x] ~~デザインスタイル選定~~（利用者に見える画面の見た目が変わらない）
- [x] ~~画面一覧・画面遷移~~（利用者に見える画面の見た目が変わらない）
- [x] ~~単一ユースケース設計~~（影響なし: 配信の設定の変更だけ）
- [x] ~~モック作成~~（利用者に見える画面の見た目が変わらない）
- [x] ~~インターフェース定義設計~~（影響なし: フック・MCP サーバーの入出力は変わらない）
- [x] ~~部品設計~~（画面の部品を持たない）
- [x] ~~画面設計~~（変更が画面に及ばない）
- [x] ~~モジュール構成設計~~（影響なし: 実装を変えない）
- [x] ドキュメント修正（dev-docs.yaml・files.yaml・schemas/files.schema.yaml）
- [x] ~~単体テスト作成~~（実装を変えない）
- [x] ~~実装~~（実装を変えない）
- [x] ~~結合テスト作成~~（実装を変えない）
- [x] ~~E2E テスト作成~~（ユースケースの振る舞いが変わらない）
