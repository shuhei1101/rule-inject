# 反映作業「利用者の設定ファイルへの移行」を、settings.yaml が既にある端末でも env の旧キーを削除できるようにする

## 概要

tester が、スキル global-setup で settings.yaml を作成済みの端末でも、[#52](https://github.com/shuhei1101/rule-inject/pull/52) の反映作業「利用者の設定ファイルへの移行」を実行して、`settings.json` の `env` に残った旧キー（`RULE_INJECT_INDEXES_USER` など）を削除できるようになる。

## 背景

[Issue #116](https://github.com/shuhei1101/rule-inject/issues/116) の不具合。
v0.2.4 を master へ入れた後、反映作業を `--dry-run` で実行すると、前提確認で「`~/.config/rule-inject/settings.yaml` が既にあり、移す内容と異なります」と止まった（[記録](https://github.com/shuhei1101/rule-inject/issues/53#issuecomment-6726959109)）。
移行のスクリプトは settings.yaml が無いか、移す内容と同じであることを前提にしている。
[#52](https://github.com/shuhei1101/rule-inject/pull/52) のマージから v0.2.4 のリリースまでの間に develop へ入った global-setup（[#106](https://github.com/shuhei1101/rule-inject/pull/106)）が、`version`・`global.server_service` を持つ settings.yaml を先に作ったため、前提が崩れた。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と変更箇所の由来 |
