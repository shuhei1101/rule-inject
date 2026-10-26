"""要件の書式で文書の場所と範囲を結果に載せる、PoC の検証用の MCP サーバー。"""

from __future__ import annotations

from pydantic import BaseModel

from mcp.server.mcpserver import MCPServer

# 大きい結果で並べる文書の数と、1 文書の本文の行数（合計が MCP の出力の上限を超える長さ）
LARGE_DOC_COUNT = 40
LARGE_DOC_LINES = 400

mcp = MCPServer("poc-docs")


class DocItem(BaseModel):
    """json の結果の 1 項目。"""

    path: str
    scope: str
    body: str


class DocList(BaseModel):
    """json の結果。"""

    items: list[DocItem]


def _body(index: int, lines: int) -> str:
    """文書の本文を組み立てる。"""
    return "\n".join(f"文書 {index} の {n} 行目の本文です。" for n in range(lines))


def _markdown(docs: list[tuple[str, str, str]]) -> str:
    """文書を <document> で包んだ markdown を組み立てる。"""
    return "\n\n".join(
        f'<document path="{path}" scope="{scope}">\n{body}\n</document>' for path, scope, body in docs
    )


@mcp.tool()
def small_markdown() -> str:
    """scope=full と scope=summary の文書を 1 つずつ markdown で返す。"""
    return _markdown(
        [
            ("/rules/full.md", "full", _body(0, 3)),
            ("/rules/summary.md", "summary", "説明だけ"),
        ]
    )


@mcp.tool()
def small_json() -> DocList:
    """scope=full と scope=section の項目を json の構造化された結果で返す。"""
    return DocList(
        items=[
            DocItem(path="/rules/full.md", scope="full", body=_body(0, 3)),
            DocItem(path="/rules/section.md", scope="section", body="抜粋"),
        ]
    )


@mcp.tool()
def large_markdown() -> str:
    """scope=full の文書を上限を超える長さで並べた markdown を返す。"""
    return _markdown(
        [(f"/rules/large-{i}.md", "full", _body(i, LARGE_DOC_LINES)) for i in range(LARGE_DOC_COUNT)]
    )


@mcp.tool()
def large_json() -> DocList:
    """scope=full の項目を上限を超える長さで並べた json の構造化された結果を返す。"""
    return DocList(
        items=[
            DocItem(path=f"/rules/large-{i}.md", scope="full", body=_body(i, LARGE_DOC_LINES))
            for i in range(LARGE_DOC_COUNT)
        ]
    )


if __name__ == "__main__":
    mcp.run()
