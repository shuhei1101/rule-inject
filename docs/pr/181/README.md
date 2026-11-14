# 配信元の設定の Schema を knowledge の Schema の参照へ切り替え、schemas/ の Schema のコピーを削除する

## 概要

配信元の設定 `project-index.yaml` の `documents[].schema` を knowledge の Schema の参照へ切り替え、`schemas/` の Schema のコピーを削除して、設計書を新しい Schema の検査に合格させる。

## 背景

[Issue #178](https://github.com/shuhei1101/rule-inject/issues/178) の要望。
[shuhei1101/ai-monitor#3188](https://github.com/shuhei1101/ai-monitor/issues/3188) で、設計書の Schema は knowledge が持つ 1 つだけにし、各プロジェクトはコピーを持たないと決めた。
このリポジトリの `project-index.yaml` は `layout` の行だけが knowledge の Schema を参照し、他の行は `schemas/` のコピーを指している。
`interface`・`scenario` のコピーは `flow` を ```` ```mermaid ```` と定めたままで、mdmark の図へ書き換えた設計書（[#174](https://github.com/shuhei1101/rule-inject/pull/174)）と記述が合わない。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
| [プラグイン](./プラグイン.md) | 配信元の設定・Schema・設計書の計画書 |
