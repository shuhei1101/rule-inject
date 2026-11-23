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

## テスト結果

### 単体

### 結合
