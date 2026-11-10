# モジュール構成の本文を移行し、ファイル単位の文書に lead を記載する

## 概要

`docs/module/` のモジュール構成（MOD-122-1〜62）の本文（lead 以外）を規約『表し方の優先順位』と規約『文章の書き方』に合わせ、ファイル単位の文書（MOD-122-1〜51）に lead を記載する。

## 背景

[Issue #129](https://github.com/shuhei1101/rule-inject/issues/129) の要望。
[PR #125](https://github.com/shuhei1101/rule-inject/pull/125) は設計書の lead と管理用の YAML だけを移行し、設計書の本文は分類ごとの Issue へ分けた。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
