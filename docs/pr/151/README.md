# src・tests・hooks・設計書・docs/guide に残る AI slop の単語を置き換える

## 概要

`src`・`tests`・`hooks`・設計書・`docs/guide` に残る AI slop の単語を、規約『文章の書き方』の対応表の単語へ置き換える。

## 背景

[Issue #150](https://github.com/shuhei1101/rule-inject/issues/150) の要望。
[PR #148](https://github.com/shuhei1101/rule-inject/pull/148)（[Issue #143](https://github.com/shuhei1101/rule-inject/issues/143)）はインターフェース定義のフロー名・シナリオの図の一部・結合テストとコードの一部の文言だけを置き換え、同じ単語がその範囲の外に残っている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
