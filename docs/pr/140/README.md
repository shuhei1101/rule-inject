# 用語集を新設し、rule-inject の用語を登録する

## 概要

dev-docs の配信元に `alias_type: term` の用語集を新設し、rule-inject の用語と言い換えを登録する。

## 背景

[Issue #131](https://github.com/shuhei1101/rule-inject/issues/131) の要望。
[Issue #99](https://github.com/shuhei1101/rule-inject/issues/99) の「エイリアスと用語」の改善は、作業 PR [#125](https://github.com/shuhei1101/rule-inject/pull/125) で設計書と公開ドキュメントの行に `alias_type: doc` を追加するところまでで止めた。
リポジトリに用語を持つ文書の種類も Schema も無いため、用語集は #125 のスコープ外にした。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
