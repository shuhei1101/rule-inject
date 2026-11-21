# MCP サーバーの instructions とツールの description をプロンプトファイルへ移し、読み込む仕組みを作る

## 概要

MCP サーバーの instructions とツールの description の本文をプロンプトファイルへ移し、サーバーの組み立てでプロンプトファイルを読み込んで登録する。

## 背景

[Issue #202](https://github.com/shuhei1101/rule-inject/issues/202) の要望。
knowledge のテンプレート『MCP サーバーの定義』は instructions とツールの description の本文をプロンプトファイルに記載すると定めるが、[app.py](https://github.com/shuhei1101/rule-inject/blob/85706a28dc7d9419455f6997797684b5168b5c68/src/rule_inject/server/app.py) は `SERVER_INSTRUCTIONS` とツール関数の docstring に本文を直接記載している。
[PR #201](https://github.com/shuhei1101/rule-inject/pull/201) で MCP サーバーの設計書を作った際に、配置先の移行をスコープ外に残した。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [MCP サーバー](./MCP%20サーバー.mark.md) | MCP サーバーの計画書 |
