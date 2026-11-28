# 開発ドキュメントのタブとサイドバーを規約『開発ドキュメントのナビゲーション』に従って nav で定義し、目次を並べない

## 概要

開発ドキュメントサーバー（dev-docs）の画面で、配信元 `rule-inject` の読む人が、入口の文書（はじめに・使い方）を左のタブから開き、サイドバーのグループで目的の文書を探せるようになる。

## 背景

[Issue #189](https://github.com/shuhei1101/rule-inject/issues/189) の要望。
配信元 `rule-inject` の配信の設定（`project-index.yaml`）に `nav` が無く、画面のタブが文書の行ごとの 20 件の並びのままで、画面の幅に収まらない。入口の文書が右の方にあり、フォルダの目次（`index`）もタブ「目次」として並ぶ。
ほかのプロジェクト（project-index・alias-inject・gui-support など）は、knowledge の規約 `dev-docs-navigation` の並びの `nav` に移っている。
ユーザーの[追加の指示](https://github.com/shuhei1101/rule-inject/issues/189#issuecomment-7236821374)で、サイドバーの `group` の 2 階層までの入れ子（判定フローチャート `flowchart-sidebar-group-split`）と、タブの 7 つの並びを範囲に含める。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [画面の確認](./画面の確認.mark.md) | dev-docs の画面の撮影と、結合テストの実行範囲 |
