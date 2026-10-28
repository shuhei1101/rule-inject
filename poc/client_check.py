"""PoC: Streamable HTTP のクライアントから echo を呼び、戻り値を確かめる。"""
import asyncio
import sys

from mcp.client import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main(url: str) -> None:
    async with streamable_http_client(url) as (read, write, *_):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", [tool.name for tool in tools.tools])
            result = await session.call_tool("echo", {"text": "hello"})
            print("result:", result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
