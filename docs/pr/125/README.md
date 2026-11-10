# 既存の文書を mdmark の書き方と表し方の優先順位（図 → 表 → 箇条書き → 文）に移行する

## 概要

rule-inject の文書を、mdmark の書き方と「図 → 表 → 箇条書き → 文」の表し方に揃え、タグ・エイリアス・description・関連を今の規約で付け直す。

## 背景

[Issue #99](https://github.com/shuhei1101/rule-inject/issues/99) の要望。
dev-docs への移行で文書の配信は揃ったが、文書の中身は旧い書き方のまま（Mermaid の図・文の羅列・接頭辞の無いタグ・AI slop の単語）のものが多い。
`dev/` は [PR #122](https://github.com/shuhei1101/rule-inject/pull/122) で廃止され、文書は `docs/` の種類のフォルダにまとまった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
