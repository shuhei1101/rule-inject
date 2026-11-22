# SKILL.md の自動生成の登録を廃止し、SKILL.md を手で記載するファイルにする

## 概要

配信元の設定から SKILL.md の生成・検査の登録を削除し、`skills/` の SKILL.md を設計書を見ながら手で記載するファイルにする。

## 背景

[Issue #210](https://github.com/shuhei1101/rule-inject/issues/210) の要望。
[#209](https://github.com/shuhei1101/rule-inject/pull/209) で、SKILL.md の生成を `project-index skill-md` へ切り替え、`project-index.yaml` の `generators[]`・`validators[]` に登録した。
ユーザーの判断（[shuhei1101/knowledge#544 のコメント](https://github.com/shuhei1101/knowledge/pull/544#issuecomment-7074367837)）で、SKILL.md は設計書から生成せず、設計書と SKILL.md の二重管理にして食い違いはレビューで確認することになった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [プラグイン](./プラグイン.mark.md) | プラグインの計画書 |
