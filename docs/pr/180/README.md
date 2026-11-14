# 空のルール索引 docs/rules.yaml を削除し、ルール索引を直下の rules.yaml にまとめる

## 概要

ルール索引を直下の `rules.yaml` の 1 か所にまとめ、`docs/` の直下に目次と GitHub Pages のファイルだけを置く。

## 背景

[Issue #177](https://github.com/shuhei1101/rule-inject/issues/177) の要望。[#173](https://github.com/shuhei1101/rule-inject/pull/173)（起点 Issue [#114](https://github.com/shuhei1101/rule-inject/issues/114)）で作成したフォルダ構成の設計書 `docs/layout/LAY-173-1.yaml` を、規約『フォルダ構成の切り方とレビュー』の観点「同じ種類が散る」「種類が混ざる」で確認して見つかった。
`docs/rules.yaml` は `rules: []` だけの空の索引で、AI Monitor の端末の設定の `rule_indexes` から 2 つめの索引として指されている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [反映作業](./反映作業/index.yaml) | AI Monitor の端末の設定の `rule_indexes` の行の削除 |
