# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/scenario/SC-122-4.yaml](https://github.com/shuhei1101/rule-inject/blob/91921ab/docs/scenario/SC-122-4.yaml) | サーバーの起動と停止 | 名前を変える 1 件 |
| ドキュメント | [docs/scenario/SC-122-12.yaml](https://github.com/shuhei1101/rule-inject/blob/91921ab/docs/scenario/SC-122-12.yaml) | 操作に当たるルールを検索する | 名前を変える 2 件。1 件は SC-122-25 が参照している |
| ドキュメント | [docs/scenario/SC-122-19.yaml](https://github.com/shuhei1101/rule-inject/blob/91921ab/docs/scenario/SC-122-19.yaml) | 索引のエントリの編集 | 名前を変える 1 件 |
| ドキュメント | [docs/scenario/SC-122-20.yaml](https://github.com/shuhei1101/rule-inject/blob/91921ab/docs/scenario/SC-122-20.yaml) | 索引のチェック | 名前を変える 3 件。図のメッセージにも「ユーザー全体の索引も確かめる」がある |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| シナリオ名 | 要件.md の表の新しい名前にする | - |
| SC-122-20 の図のメッセージ | シナリオ名と同じく「確かめる」を「確認する」にする | - |

## テスト結果

なし（シナリオの名前と参照だけを変え、コードを変えないため、関係する単体・結合テストが無い）
