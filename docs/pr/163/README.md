# 配信元・画面としての dev-docs の記述と dev-docs.yaml を、project-index への移行に合わせて見直す

## 概要

配信元の設定 `dev-docs.yaml` と、配信元・画面としての dev-docs を指す公開ドキュメント・スキーマの説明文を、project-index への移行に合わせて直す。

## 背景

[Issue #162](https://github.com/shuhei1101/rule-inject/issues/162) の要望。
[PR #159](https://github.com/shuhei1101/rule-inject/pull/159)（[Issue #158](https://github.com/shuhei1101/rule-inject/issues/158)）は文書の MCP のツールの完全名と `check_indexes` の接続先を project-index へ書き換えたが、配信元・画面としての dev-docs の記述は [shuhei1101/project-index#15](https://github.com/shuhei1101/project-index/pull/15) の要件で `dev-docs.yaml` の移行が未確定だったため、この Issue へ回した。
その後 [shuhei1101/project-index#19](https://github.com/shuhei1101/project-index/pull/19) で、project-index 自身の配信元の設定は `project-index.yaml` へ改名された。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
