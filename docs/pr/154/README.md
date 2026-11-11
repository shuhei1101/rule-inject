# schemas・skills・.claude-plugin・docs の目次と索引に残る AI slop の単語を置き換える

## 概要

`schemas/glossary.schema.yaml`・`skills`・`.claude-plugin`・`docs/README.md`・`docs/rules.yaml` に残る AI slop の単語を、規約『文章の書き方』の対応表の単語へ置き換える。

## 背景

[Issue #152](https://github.com/shuhei1101/rule-inject/issues/152) の要望。
[PR #151](https://github.com/shuhei1101/rule-inject/pull/151)（[Issue #150](https://github.com/shuhei1101/rule-inject/issues/150)）は `src`・`tests`・`hooks`・設計書・`docs/guide` の単語だけを置き換え、同じ単語がその範囲の外に残っている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
