# インターフェース定義の本文を mdmark の書き方と表し方の優先順位へ移行する

## 概要

`docs/interface/` のインターフェース定義（IF-122-1〜22）の本文（lead 以外）を、規約『表し方の優先順位』と規約『文章の書き方』に合わせる。

## 背景

[Issue #128](https://github.com/shuhei1101/rule-inject/issues/128) の要望。
[PR #125](https://github.com/shuhei1101/rule-inject/pull/125) は設計書の lead と管理用の YAML だけを移行し、設計書の本文は分類ごとの Issue へ分けた。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | プラグインの計画書（IF-122-13〜22） |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書（IF-122-1〜12） |