# SKILL.md の生成を project-index skill-md へ切り替え、python -m rule_inject.build_skills を廃止する

## 概要

このリポジトリの SKILL.md を `project-index skill-md` で生成・検査し、独自の生成のコマンド `python -m rule_inject.build_skills` を廃止する。

## 背景

[Issue #208](https://github.com/shuhei1101/rule-inject/issues/208) の要望。
[shuhei1101/project-index#243](https://github.com/shuhei1101/project-index/pull/243) で、`type: skill` のエージェントフローから SKILL.md を生成・検査する `project-index skill-md`（project-index の IF-37）が入った。
このリポジトリは同じ約束で SKILL.md を組み立てる独自のコマンド（[IF-122-24『SKILL.md の生成』](https://github.com/shuhei1101/rule-inject/blob/61ce8df/docs/interface/IF-122-24.py.yaml)）を持ち、書式の約束を変えるたびに project-index・knowledge・rule-inject の 3 か所を合わせる必要がある。
依頼元は [shuhei1101/project-index#244](https://github.com/shuhei1101/project-index/issues/244)。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [プラグイン](./プラグイン.mark.md) | プラグインの計画書 |
