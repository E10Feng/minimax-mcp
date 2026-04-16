import asyncio
import json
import os
import subprocess

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

MINIMAX_BASE_URL = "https://api.minimax.io"

app = Server("minimax-mcp")


def _get_api_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY")
    if not key:
        raise RuntimeError(
            "MINIMAX_API_KEY environment variable is required. "
            "Set it in your shell profile: export MINIMAX_API_KEY=<your_key>"
        )
    return key


def main() -> None:
    asyncio.run(_async_main())


async def _async_main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
