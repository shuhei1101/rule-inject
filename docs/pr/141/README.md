# シナリオ名の AI slop の単語を、参照する側と一緒に置き換える

## 概要

シナリオ名（`scenarios[].name`）に残る AI slop の単語を対応表の単語へ置き換え、名前を参照する `uses`・図の `click` とラベルも同じ名前に書き換える。

## 背景

[Issue #138](https://github.com/shuhei1101/rule-inject/issues/138) の要望。
[PR #134](https://github.com/shuhei1101/rule-inject/pull/134)（[Issue #127](https://github.com/shuhei1101/rule-inject/issues/127)）でシナリオの本文の AI slop の単語を置き換えたが、シナリオ名は参照されるキーのためスコープ外にした。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
