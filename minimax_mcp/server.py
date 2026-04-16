import asyncio
import json
import os
import subprocess

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

ANTHROPIC_BASE_URL = "https://api.minimax.io"
SUBPROCESS_TIMEOUT_SECONDS = 300

app = Server("minimax-mcp")


def _get_api_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY")
    if not key:
        raise RuntimeError(
            "MINIMAX_API_KEY environment variable is required. "
            "Set it in your shell profile: export MINIMAX_API_KEY=<your_key>"
        )
    return key


def _run_minimax_subagent(task: str, context: str, api_key: str) -> str:
    """Spawn a claude subprocess using Minimax as the backend and return its output."""
    if context:
        prompt = f"Context:\n{context}\n\nTask:\n{task}"
    else:
        prompt = task

    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = ANTHROPIC_BASE_URL
    env["ANTHROPIC_API_KEY"] = api_key

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            env=env,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )

        if result.returncode != 0:
            return f"Minimax subagent error:\n{result.stderr or result.stdout}"

        # Try to parse structured JSON output from claude -p
        try:
            parsed = json.loads(result.stdout)
            return parsed.get("result", result.stdout)
        except (json.JSONDecodeError, AttributeError):
            return result.stdout

    except subprocess.TimeoutExpired:
        return (
            f"Minimax subagent timed out after {SUBPROCESS_TIMEOUT_SECONDS // 60} minutes. "
            "Try breaking the task into smaller pieces."
        )
    except FileNotFoundError:
        return (
            "Error: `claude` CLI not found. "
            "Ensure Claude Code is installed: https://claude.ai/code"
        )


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="minimax_code",
            description=(
                "Delegate coding implementation tasks to a Minimax-backed Claude Code subprocess. "
                "Use for writing code, editing files, implementing features, refactoring. "
                "Reserve the main Claude session for planning, chatting, and high-level decisions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Full description of what to implement",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional: relevant file contents, prior decisions, constraints",
                    },
                },
                "required": ["task"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "minimax_code":
        raise ValueError(f"Unknown tool: {name}")

    api_key = _get_api_key()
    task = arguments["task"]
    context = arguments.get("context", "")

    loop = asyncio.get_event_loop()
    output = await loop.run_in_executor(
        None, _run_minimax_subagent, task, context, api_key
    )
    return [TextContent(type="text", text=output)]


def main() -> None:
    asyncio.run(_async_main())


async def _async_main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
