# シナリオの本文を mdmark の書き方と表し方の優先順位へ移行する

## 概要

`docs/scenario/` のシナリオ（SC-122-1〜25）の本文（lead 以外）を、mdmark の書き方と表し方の優先順位（図 → 表 → 箇条書き → 文）に統一する。

## 背景

[Issue #127](https://github.com/shuhei1101/rule-inject/issues/127) の要望。
[PR #125](https://github.com/shuhei1101/rule-inject/pull/125) では設計書の lead と管理用の YAML だけを移行し、本文は設計書の分類ごとの Issue へ分けた（[確認事項](https://github.com/shuhei1101/rule-inject/pull/125#discussion_r4528130772)）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
