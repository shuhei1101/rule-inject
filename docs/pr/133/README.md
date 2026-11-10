# 新しいファイルの作り方の決まりを SessionStart の注入から MCP サーバーの instructions へ移す

## 概要

Claude Code のセッションとサブエージェントが、rule-inject の MCP サーバーの instructions から、新しいファイルを空で作ってから中身を記載する決まりを受け取れるようになる。

## 背景

[Issue #124](https://github.com/shuhei1101/rule-inject/issues/124) の要望。
rule-inject は SessionStart のフック（`work_rules`）で、新しいファイルは空で作ってから中身を記載する決まりを注入している。
knowledge の規約『注入文の書き分けと書き方』は、MCP サーバーを持つプラグインの使い方の案内を MCP の instructions に記載すると定めており、MCP サーバーを持つようになった rule-inject の実体と合っていない。
SessionStart の注入はサブエージェントに届かない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | プラグインの計画書 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
