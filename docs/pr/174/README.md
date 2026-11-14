# インターフェース定義とシナリオの Mermaid の図を mdmark の図へ書き換える

## 概要

インターフェース定義とシナリオの `flow` の Mermaid の図を、mdmark の map の図へ書き換える。

## 背景

[Issue #145](https://github.com/shuhei1101/rule-inject/issues/145) の要望。
[Issue #126](https://github.com/shuhei1101/rule-inject/issues/126) から、ユーザーの回答（[確認事項への「a」](https://github.com/shuhei1101/rule-inject/issues/126#issuecomment-6777573626)）で設計書の分を切り出した。
依存の [shuhei1101/knowledge#251](https://github.com/shuhei1101/knowledge/issues/251)・[shuhei1101/knowledge#246](https://github.com/shuhei1101/knowledge/issues/246)・[shuhei1101/ai-monitor#3188](https://github.com/shuhei1101/ai-monitor/issues/3188) は閉じており、knowledge の Schema（`design-schemas/v8.0.0` 以降）はインターフェース定義・シナリオの `flow` を mdmark の map の図と定めている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | プラグインのインターフェース定義・シナリオの計画書 |
| [MCP サーバー](./MCP%20サーバー.md) | MCP サーバーのインターフェース定義・シナリオの計画書 |
