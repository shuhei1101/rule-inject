# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/interface/](https://github.com/shuhei1101/rule-inject/blob/develop/docs/interface/index.yaml) | MCP のツールのインターフェース定義（IF-122-1〜12） | Mermaid を含む（IF-122-1・2・6・7・8・11 の 6 件） |
| ドキュメント | [docs/module/](https://github.com/shuhei1101/rule-inject/blob/develop/docs/module/index.yaml) | MCP サーバーのモジュール構成 | ファイル単位の文書は description（`lead`）が空 |
| ドキュメント | [docs/external-api/](https://github.com/shuhei1101/rule-inject/blob/develop/docs/external-api/index.yaml)・[docs/library/](https://github.com/shuhei1101/rule-inject/blob/develop/docs/library/index.yaml) | dev-docs と外部ライブラリのリファレンス | - |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 設計書の本文 | この PR では変えない | スコープ外（ユーザーへ確認中） |
| 設計書の description | `lead` を description のチェックシートに合わせる | IF-122-11 など 120 字を超える `lead` を削る |

## テスト結果

なし（文書とメタデータだけを変え、コードを変えないため、関係する単体・結合テストが無い）
