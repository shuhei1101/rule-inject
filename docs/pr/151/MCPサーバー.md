# MCP サーバー

## 現状

origin/develop [639080c](https://github.com/shuhei1101/rule-inject/commit/639080c) で NG の単語（「読む」を除く）を持つファイル。

<!-- table: data -->

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/scenario/](https://github.com/shuhei1101/rule-inject/tree/639080c/docs/scenario) | MCP のツールとサーバーのシナリオ | SC-122-1〜5・9・12・14・15・19・20・22〜25 と `index.yaml`・`README.md` の説明と図のメッセージ |
| ドキュメント | [docs/interface/](https://github.com/shuhei1101/rule-inject/tree/639080c/docs/interface) | MCP のツールとサーバーのインターフェース定義 | IF-122-1〜8・11・12 と `index.yaml`・`README.md` の summary・notes・constraint・図のメッセージ・文言 |
| ドキュメント | [docs/module/](https://github.com/shuhei1101/rule-inject/tree/639080c/docs/module) | MCP サーバーのモジュール構成 | MOD-122-12・34〜38・40・42〜44・52 と `index.yaml`・`README.md` の説明と docstring |
| 実装 | [src/rule_inject/server/](https://github.com/shuhei1101/rule-inject/tree/639080c/src/rule_inject/server) | サーバーとツール | ツールの説明文・docstring・コメント・エラーと応答の文言 |
| 実装 | [src/rule_inject/features/index/check/](https://github.com/shuhei1101/rule-inject/tree/639080c/src/rule_inject/features/index/check) | 索引のチェック | docstring・コメント・違反の文言・`index.schema.yaml` の title・description |
| 実装 | [src/rule_inject/features/index/edit/](https://github.com/shuhei1101/rule-inject/tree/639080c/src/rule_inject/features/index/edit) | エントリの編集 | docstring・コメント・エラーの文言 |
| テスト | [tests/unit/rule_inject/server/](https://github.com/shuhei1101/rule-inject/tree/639080c/tests/unit/rule_inject/server)・[tests/unit/rule_inject/features/index/check/](https://github.com/shuhei1101/rule-inject/tree/639080c/tests/unit/rule_inject/features/index/check)・[tests/unit/rule_inject/features/index/edit/](https://github.com/shuhei1101/rule-inject/tree/639080c/tests/unit/rule_inject/features/index/edit) | サーバー・索引のチェック・エントリの編集の単体テスト | docstring と文言の期待値 |
| テスト | [tests/integration/server/](https://github.com/shuhei1101/rule-inject/tree/639080c/tests/integration/server) | MCP のツールの結合テスト | docstring と文言の期待値 |

<!-- /table -->

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 設計書 | 説明・図のメッセージ・文言の NG の単語を要件.md の言い回しへ置き換える | 流れ・入出力は変えない |
| ツールの説明文 | 同上。同じ項目を説明する `docs/guide/MCPツール.md` も同じ言い回しにする | - |
| docstring・コメント | 同上 | 処理は変えない |
| エラー・違反・応答の文言、`index.schema.yaml` の title・description | 同上。文言を記載する設計書・公開ドキュメントとテストの期待値も同じ文言にする | - |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| 単一ユースケース設計 | `639080c..d2ddca3` | - |
