# 実装済みなのに status: planned のままの設計書の行を、実装の状態に合わせる

## 概要

設計書の `status: planned` の行のうち実装済みの行から `status` を外し、設計書の状態を実装に合わせる。

## 背景

[Issue #161](https://github.com/shuhei1101/rule-inject/issues/161) の要望。[#159](https://github.com/shuhei1101/rule-inject/pull/159) のレビューで、アーキテクチャ図の外部システム project-index の行が、`check_indexes` のタグの検査が実装済みなのに `status: planned` のままと分かった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCP%20サーバー.md) | MCP サーバーの計画書 |
