# ルール索引の文書の MCP の既読を、切り替えの途中も dev-docs と project-index の両方の名前で取る

## 概要

dev-docs のプラグインと project-index のプラグインのどちらの名前で文書の MCP の `search_docs` を呼んでも、このリポジトリの索引 `rules.yaml` のルールを既読にする。

## 背景

[Issue #169](https://github.com/shuhei1101/rule-inject/issues/169) の要望。
文書の MCP は dev-docs から project-index に切り出された（shuhei1101/dev-docs#114）。
[PR #159](https://github.com/shuhei1101/rule-inject/pull/159) で `rules.yaml` の `read_tool.tool` は project-index の名前に書き換わった。
切り替えの途中に dev-docs の名前で呼んだときに既読になるかを、既読の記録のフック `record_read` で実測した（[要件](./要件.md)）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
