# ルール索引のエントリに名前を持たせ、dev-docs のサイドバーで見分けられるようにする

## 概要

dev-docs のタブ「規約」のサイドバーで、ルール索引のエントリをどのルールのエントリか見分けられる名前で表示する。

## 背景

[Issue #226](https://github.com/shuhei1101/rule-inject/issues/226) の要望。
配信元の設定（`project-index.yaml`）の行 `rule_index` の文書（`rules.yaml` の `rules` の要素）は名前を持たず、サイドバーに `rules.yaml#0`〜`rules.yaml#9` と表示される。
[#223](https://github.com/shuhei1101/rule-inject/pull/223) で `metadata` の `name` を `rule` にしたが、10 件中 9 件が `!{KNOWLEDGE_ROOT}/docs/rule/...` の同じ頭になってサイドバーで切れたため取り消した（[1f9af63](https://github.com/shuhei1101/rule-inject/commit/1f9af63) → [31867d0](https://github.com/shuhei1101/rule-inject/commit/31867d0)）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [プラグイン](./プラグイン.mark.md) | フックの索引の読み取りの計画書 |
| [MCP サーバー](./MCP%20サーバー.mark.md) | 索引のスキーマ・検査・エントリの編集・一覧のツールの計画書 |
