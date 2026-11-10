# mdmark.config.yaml を作り、公開ドキュメントに mdmark の check を実行できるようにする

## 概要

公開ドキュメント（`docs/guide/`）に mdmark の `check` を実行できるようにし、出た問題を修正する。

## 背景

[Issue #132](https://github.com/shuhei1101/rule-inject/issues/132) の要望。
[Issue #99](https://github.com/shuhei1101/rule-inject/issues/99) の手順「検査」は mdmark の `check` で合格することを求めるが、リポジトリに `mdmark.config.yaml` が無く、作業 PR [#125](https://github.com/shuhei1101/rule-inject/pull/125) では公開ドキュメントに `check` を実行できなかったためスコープ外にした。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理・更新ドキュメント・スコープ外 |
| [タスク一覧](./タスク一覧.yaml) | 工程ごとの状態 |
