# MCP サーバーとスキルの設計書を knowledge のテンプレートで作成し、実装を設計書に合わせる

## 概要

rule-inject の MCP サーバーとスキル（global-setup・setup）の設計書を knowledge のテンプレートで作成し、実装を設計書に合わせる。

## 背景

[Issue #200](https://github.com/shuhei1101/rule-inject/issues/200) の要望。
[shuhei1101/ai-monitor#3743](https://github.com/shuhei1101/ai-monitor/issues/3743) で AI Monitor の設計の工程に「エージェント・MCP サーバー設計」「エージェントフロー・LLM 呼び出し設計」が入ったが、このリポジトリの MCP サーバーとスキルには knowledge のテンプレート（`template-mcp-server`・`template-agent-flow`）に沿った設計書が無い。
今は MCP サーバーの instructions とツールの description が `src/rule_inject/server/app.py` に直接書かれ、スキルの `SKILL.md` は手で書いた原本になっている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [MCP サーバー](./MCP%20サーバー.mark.md) | MCP サーバーの計画書 |
| [プラグイン](./プラグイン.mark.md) | プラグイン（スキル）の計画書 |
| [反映作業](./反映作業/index.yaml) | 配信元の設定への種類の行の追加 |
