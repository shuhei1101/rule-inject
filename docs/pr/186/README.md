# AI Monitor v0.4.0 の配布物へ追従する

## 概要

rule-inject が準拠する AI Monitor の配布物を v0.3.0 から v0.4.0 へ上げ、成果物を v0.4.0 のサイトのレイアウト・配信設定・規約・テンプレートに合わせる。

## 背景

[Issue #185](https://github.com/shuhei1101/rule-inject/issues/185) の要望。
AI Monitor の v0.4.0 のタグで配布物が変わり、配布元が追従 Issue を起票した。
develop の `ai-monitor-version.ini` と `ai-monitor-theme.yaml` は `v0.3.0` のままになっている。
追従 Issue の配布先の反映作業のうち、索引の移動・dev-docs への移行・スキーマの参照への移行・データの設計書の作成は [#165](https://github.com/shuhei1101/rule-inject/pull/165)・[#180](https://github.com/shuhei1101/rule-inject/pull/180)・[#181](https://github.com/shuhei1101/rule-inject/pull/181) で済んでいる。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [反映作業](./反映作業/index.yaml) | 配布先の反映作業の一覧 |
