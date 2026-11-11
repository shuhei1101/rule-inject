# MCP サーバーの instructions に rule-inject の MCP のツールの使い分けを追加する

## 概要

Claude Code のセッションとサブエージェントが、rule-inject の MCP サーバーの instructions から、いつこの MCP のツールを呼ぶかと grep・Read との使い分けを受け取れるようになる。

## 背景

[Issue #146](https://github.com/shuhei1101/rule-inject/issues/146) の要望。
[#133](https://github.com/shuhei1101/rule-inject/pull/133)（起点 [#124](https://github.com/shuhei1101/rule-inject/issues/124)）で MCP サーバーの instructions を新設し、新しいファイルの作り方の決まりだけを記載した。
knowledge の規約『注入文の書き分けと書き方』は、MCP の instructions に、いつこの MCP を探すか・grep・Read との使い分け・ツール間の順序を記載すると定めている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [MCP サーバー](./MCPサーバー.md) | MCP サーバーの計画書 |
