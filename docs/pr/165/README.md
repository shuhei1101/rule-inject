# 配信元の設定 dev-docs.yaml を project-index.yaml へ改名し、端末の設定の config を書き換える

## 概要

リポジトリの直下の配信元の設定 `dev-docs.yaml` を `project-index.yaml` へ改名し、端末の設定の配信元 rule-inject の `config` を改名後のパスへ書き換える。

## 背景

[#164](https://github.com/shuhei1101/rule-inject/issues/164) の要望。
[#163](https://github.com/shuhei1101/rule-inject/pull/163)（起点 [#162](https://github.com/shuhei1101/rule-inject/issues/162)）で `dev-docs.yaml` の `$schema` を project-index の schema にし、改名は [shuhei1101/project-index#27](https://github.com/shuhei1101/project-index/issues/27) の解消を待つためスコープ外にした。
依存の #162 と shuhei1101/project-index#27 は解消している。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [反映作業](./反映作業/index.yaml) | 端末の設定の書き換え |
