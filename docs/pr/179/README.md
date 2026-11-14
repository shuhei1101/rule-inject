# .gitignore と設計書の gitignore[] に tmp/ と .claude/worktrees/ を追加する

## 概要

`.gitignore` とフォルダ構成の設計書の `gitignore[]` に、一時ファイルの `tmp/` と worktree の `.claude/worktrees/` を追加し、両者を一致させる。

## 背景

[Issue #175](https://github.com/shuhei1101/rule-inject/issues/175) の要望。
[#173](https://github.com/shuhei1101/rule-inject/pull/173) で作成したフォルダ構成の設計書 `docs/layout/LAY-173-1.yaml` を「管理しないもの」の観点で確認して見つかった。
`.gitignore` に `tmp/` が無く、`.claude/worktrees/` はクローンの `.git/info/exclude` だけが除外しているため、別のクローンでは Git の管理に入る。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
