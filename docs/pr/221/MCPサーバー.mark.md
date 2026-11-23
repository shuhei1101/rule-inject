# MCPサーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| 設定 | [project-index.yaml](https://github.com/shuhei1101/rule-inject/blob/9ca6646/project-index.yaml) | 配信元の設定 | `direct_commit` が無い |
| 端末の設定 | `~/.config/project-index/settings.yaml` の `sources[]` の `rule-inject` の行 | 配信元の登録 | `direct_commit` が無い |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| `direct_commit` | `project-index.yaml` の `documents` の前に `direct_commit: {branch: develop, kinds: [...]}` を追加する | 許可する種類は [要件](./要件.mark.md) の表 |
| 配信元の設定の検査 | 変更後の `project-index.yaml` を project-index の配信元の設定の検査に通し、違反 0 件を確認する | - |
| 端末の設定 | マージの後に `write_api_kinds` へ種類を登録する | [反映作業](./反映作業/index.yaml) |

## 実装

| 項目 | 内容 |
| --- | --- |
| `direct_commit` | [要件](./要件.mark.md) の表のとおり、[18e80b0](https://github.com/shuhei1101/rule-inject/commit/18e80b0) で追加した |
| 配信元の設定の検査 | project-index の `validate_source_config` で変更後の `project-index.yaml` を検査し、違反 0 件 |
| 反映作業のスクリプト | 端末の設定の API（`PATCH /settings/sources/rule-inject`）で書き換える。`PATCH` は再試行に乗せず、失敗したら `GET` で適用済みかを判定し直してから送り直す。`dry-run.log` には、既定の develop の worktree を指した実行（マージの前は前提確認で `failed`）と、環境変数 `RULE_INJECT_SOURCE_CONFIG` で作業ブランチの `project-index.yaml` を指した実行（計画の差分と `changed`）と、実行の後に端末の設定のファイルが変わっていないことを残した |

## テスト結果

### 単体

なし（コードを変えず、`project-index.yaml` の変更に対応する単体テストが無い）

### 結合

なし（コードを変えない）

### lint

[lint のログ](./テスト結果/20261124001819_6479214_lint.log)（全件 pass）
