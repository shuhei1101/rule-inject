"""PoC: 127.0.0.1 で Streamable HTTP の MCP サーバーを立てる。"""

import sys

from mcp.server import MCPServer

server = MCPServer("rule-inject-poc")


@server.tool()
def echo(text: str) -> str:
    """渡した文字列に印を付けて返す。"""
    return f"poc-echo:{text}"


if __name__ == "__main__":
    server.run("streamable-http", host="127.0.0.1", port=int(sys.argv[1]))
