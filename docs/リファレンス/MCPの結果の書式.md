# MCPの結果の書式

文書を返す MCP のツールが、結果に文書の場所と範囲を載せる書式

結果がこの書式に従うと、`scope` が `full` の文書のうち索引に載ったルールが、そのセッションの既読になる。
書式に従う文書が 1 つも無い結果は、索引の `read_by` で照合する（[索引の書式](./索引の書式.md)）。

## markdown

文書ごとに `<document>` で包む。
閉じタグ `</document>` の無い文書は数えない。

```markdown
<document path="/home/user/rules/python.md" scope="full">
（本文）
</document>
<document path="/home/user/rules/typescript.md" scope="summary">
（説明）
</document>
```

## json

結果の項目ごとに `path` と `scope` を文字列で持たせる。
どの深さのオブジェクトでも読む。

```json
{"items": [{"path": "/home/user/rules/python.md", "scope": "full", "body": "（本文）"}]}
```

## 属性

| 属性 | 値 | 既読になるか |
| --- | --- | --- |
| `path` | 文書のファイルのパス。`~` で始まるパス・相対パスはセッションの作業フォルダから解く。シンボリックリンクは辿らずに索引のルールの場所と比べる | `http://`・`https://` で始まる値は既読にならない |
| `scope` | `full`（全文）/ `section`（一部の見出し）/ `summary`（説明だけ） | `full` だけが既読になる |

## 既読にならない結果

- Claude Code がツールの結果の上限を超えたとして本文をファイルへ逃がした結果は、文書の場所が残らないため既読にならない
- 既読にしたルールの本文が後で変わると、未読に戻る（[ルールの案内](../はじめに/コアコンセプト/ルールの案内.md)）