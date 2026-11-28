# 設計書『テスト実行方法』に補足「画面の起動」を加え、管理用の YAML に #207 で追加したソースコードとテストの行を加える

## 概要

planner・reviewer が、作業ブランチの配信の設定で開発ドキュメントサーバー（dev-docs）の画面を開く手順を設計書『テスト実行方法』から参照できるようになり、#207 で追加したソースコードとテストが dev-docs のタブ「コード」に出るようになる。

## 背景

束の親 [Issue #227](https://github.com/shuhei1101/rule-inject/issues/227) の要望で、子は [#224](https://github.com/shuhei1101/rule-inject/issues/224)・[#225](https://github.com/shuhei1101/rule-inject/issues/225)。
どちらも作業 PR [#223](https://github.com/shuhei1101/rule-inject/pull/223) の reviewer の[対象外の逸脱の報告](https://github.com/shuhei1101/rule-inject/pull/223#discussion_r4726405203)が出所。

- #224: 設計書『テスト実行方法』の補足に「画面の起動」が無く、#223 では手順を探して一時の project-index・dev-docs を起動した
- #225: 管理用の YAML に #207 で追加した 5 ファイルの行が無く、タブ「コード」に出ない。project-index の起動時に「管理用の YAML に無いファイル」の警告が出る

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [プラグイン](./プラグイン.mark.md) | 設計書の補足と管理用の YAML の行の計画 |
