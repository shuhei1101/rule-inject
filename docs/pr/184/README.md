# project-index.yaml の instructions の files.yml の範囲を docs/guide/files.yml に合わせる

## 概要

配信元の設定 `project-index.yaml` の `instructions` から、削除した `docs/_root/files.yml` が持っていた `docs/` の直下のファイルを指す記述を除き、今ある `docs/guide/files.yml` の範囲に合わせる。

## 背景

[Issue #182](https://github.com/shuhei1101/rule-inject/issues/182) の要望。
[#180](https://github.com/shuhei1101/rule-inject/pull/180) で `docs/_root/files.yml` を削除したが、`instructions` の 2 行目は「公開ドキュメント（`docs/guide/`）と `docs/` の直下のファイルは `files.yml`」のまま残っている。
作業 PR [#181](https://github.com/shuhei1101/rule-inject/pull/181) の reviewer の対象外の逸脱の報告から切り出した。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [プラグイン](./プラグイン.md) | 配信元の設定の計画書 |
