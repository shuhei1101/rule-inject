# dev/ を廃止して文書を docs/ の種類のフォルダへまとめる

## 概要

`dev/` を廃止し、文書を `docs/` の種類のフォルダと `schemas/` へまとめ、公開範囲を各文書の `visibility` で持つ（構成は ai-monitor#3307 と同じ）。

## 背景

[Issue #120](https://github.com/shuhei1101/rule-inject/issues/120) の要望。
[shuhei1101/ai-monitor#3307](https://github.com/shuhei1101/ai-monitor/pull/3307) が AI Monitor 自身の `dev/` を廃止し、AI Monitor 以外の全ての監視対象のプロジェクトも同じ構成へ移すことを求めている。
`dev/` が残る間は、`python -m ai_monitor.design_docs` の設計書の検証・Markdown の生成が動かない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と移す先の対応 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
