# リポジトリ直下のファイルに残る AI slop の単語を置き換える

## 概要

リポジトリ直下の `README.md`・`CLAUDE.md`・`files.yaml`・`dev-docs.yaml`・`pyproject.toml`・`rules.yaml`・`settings.sample.yaml` に残る AI slop の単語を、規約『文章の書き方』の対応表の単語へ置き換える。

## 背景

[Issue #155](https://github.com/shuhei1101/rule-inject/issues/155) の要望。
[PR #151](https://github.com/shuhei1101/rule-inject/pull/151)（[Issue #150](https://github.com/shuhei1101/rule-inject/issues/150)）と [PR #154](https://github.com/shuhei1101/rule-inject/pull/154)（[Issue #152](https://github.com/shuhei1101/rule-inject/issues/152)）はどちらもリポジトリ直下のファイルを範囲に含まず、同じ単語が残っている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
