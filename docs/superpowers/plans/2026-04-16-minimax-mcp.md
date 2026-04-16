# Minimax MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python MCP server that lets the main Claude (Anthropic) session delegate all code implementation to a Minimax-backed Claude Code subprocess.

**Architecture:** A single-tool MCP server (`minimax_code`) that spawns `claude -p` subprocesses with `ANTHROPIC_BASE_URL` overridden to point to Minimax. The subprocess runs autonomously with full tool access and superpowers skills, then returns its output.

**Tech Stack:** Python 3.10+, `mcp` SDK, `uv`/`uvx` for distribution, subprocess for Claude Code spawning.

---

## File Structure

```
minimax-mcp/
  minimax_mcp/
    __init__.py       # Package init, exports main()
    server.py         # MCP server logic — the only substantive file
  tests/
    test_server.py    # Unit tests with subprocess mocking
  pyproject.toml      # Package metadata and dependencies
  README.md           # Setup and usage instructions
  docs/
    superpowers/
      specs/2026-04-16-minimax-mcp-design.md  (already written)
      plans/2026-04-16-minimax-mcp.md         (this file)
```

---

### Task 1: Project scaffold

**Files:**
- Create: `minimax_mcp/__init__.py`
- Create: `minimax_mcp/server.py` (skeleton)
- Create: `pyproject.toml`

- [ ] **Step 1: Create package directory**

```bash
cd ~/minimax-mcp
mkdir -p minimax_mcp tests
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "minimax-mcp"
version = "0.1.0"
description = "MCP server that delegates code implementation to Minimax via Claude Code subprocess"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
]

[project.scripts]
minimax-mcp = "minimax_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Create minimax_mcp/__init__.py**

```python
from minimax_mcp.server import main

__all__ = ["main"]
```

- [ ] **Step 4: Create minimax_mcp/server.py skeleton**

```python
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
```

- [ ] **Step 5: Install dependencies**

```bash
cd ~/minimax-mcp
uv sync
```

Expected: uv creates `.venv` and installs `mcp` package.

- [ ] **Step 6: Verify package is importable**

```bash
cd ~/minimax-mcp
uv run python -c "from minimax_mcp.server import main; print('OK')"
```

Expected: prints `OK`.

- [ ] **Step 7: Commit**

```bash
cd ~/minimax-mcp
git add pyproject.toml minimax_mcp/
git commit -m "feat: project scaffold with mcp dependency"
```

---

### Task 2: Implement the minimax_code tool

**Files:**
- Modify: `minimax_mcp/server.py`

- [ ] **Step 1: Write failing test first**

Create `tests/test_server.py`:

```python
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from minimax_mcp.server import _run_minimax_subagent


def test_run_minimax_subagent_returns_output():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"result": "def hello():\n    return 'world'"})
    mock_result.stderr = ""

    with patch("minimax_mcp.server.subprocess.run", return_value=mock_result) as mock_run:
        result = _run_minimax_subagent("write a hello function", "", "test-api-key")

    assert "hello" in result
    assert mock_run.called
    call_env = mock_run.call_args.kwargs["env"]
    assert call_env["ANTHROPIC_BASE_URL"] == "https://api.minimax.io"
    assert call_env["ANTHROPIC_API_KEY"] == "test-api-key"


def test_run_minimax_subagent_handles_subprocess_error():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "claude: command not found"

    with patch("minimax_mcp.server.subprocess.run", return_value=mock_result):
        result = _run_minimax_subagent("write code", "", "test-key")

    assert "error" in result.lower()


def test_run_minimax_subagent_handles_timeout():
    with patch(
        "minimax_mcp.server.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=300),
    ):
        result = _run_minimax_subagent("write code", "", "test-key")

    assert "timed out" in result.lower()


def test_run_minimax_subagent_handles_missing_claude_cli():
    with patch(
        "minimax_mcp.server.subprocess.run",
        side_effect=FileNotFoundError(),
    ):
        result = _run_minimax_subagent("write code", "", "test-key")

    assert "claude" in result.lower()
    assert "not found" in result.lower() or "install" in result.lower()


def test_run_minimax_subagent_includes_context_in_prompt():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "done"
    mock_result.stderr = ""

    with patch("minimax_mcp.server.subprocess.run", return_value=mock_result) as mock_run:
        _run_minimax_subagent("write tests", "existing code here", "test-key")

    prompt_arg = mock_run.call_args.args[0][2]  # claude -p <prompt>
    assert "existing code here" in prompt_arg
    assert "write tests" in prompt_arg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/minimax-mcp
uv run pytest tests/test_server.py -v
```

Expected: All 5 tests FAIL with `ImportError: cannot import name '_run_minimax_subagent'`

- [ ] **Step 3: Implement _run_minimax_subagent and list_tools/call_tool**

Replace the contents of `minimax_mcp/server.py`:

```python
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


def _run_minimax_subagent(task: str, context: str, api_key: str) -> str:
    """Spawn a claude subprocess using Minimax as the backend and return its output."""
    if context:
        prompt = f"Context:\n{context}\n\nTask:\n{task}"
    else:
        prompt = task

    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = MINIMAX_BASE_URL
    env["ANTHROPIC_API_KEY"] = api_key

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
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
        return "Minimax subagent timed out after 5 minutes. Try breaking the task into smaller pieces."
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

    output = _run_minimax_subagent(task, context, api_key)
    return [TextContent(type="text", text=output)]


def main() -> None:
    asyncio.run(_async_main())


async def _async_main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/minimax-mcp
uv run pytest tests/test_server.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/minimax-mcp
git add minimax_mcp/server.py tests/
git commit -m "feat: implement minimax_code tool with subprocess spawning"
```

---

### Task 3: Write README and configure Claude Code

**Files:**
- Create: `README.md`
- Modify: `~/.claude/settings.json`

- [ ] **Step 1: Write README.md**

```markdown
# minimax-mcp

MCP server that delegates code implementation to a [Minimax](https://minimax.io)-backed Claude Code subprocess. Use your main Claude (Anthropic) session for planning and chatting — delegate all coding to Minimax.

## How it works

When Claude calls `minimax_code(task)`, this server spawns a `claude -p` subprocess with `ANTHROPIC_BASE_URL` set to Minimax's endpoint. The subprocess has full tool access (Read, Write, Edit, Bash) and runs autonomously, then returns results to your main session.

## Setup

### 1. Get your Minimax API key

Sign up at [minimax.io](https://minimax.io) and copy your API key.

### 2. Set the environment variable

```bash
echo 'export MINIMAX_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

### 3. Add to Claude Code settings

Add this to `~/.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "minimax": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/E10Feng/minimax-mcp", "minimax-mcp"]
    }
  }
}
```

Claude Code will pass your `MINIMAX_API_KEY` from the environment automatically.

### 4. Restart Claude Code

The server starts automatically when Claude Code launches.

## Usage

Claude will automatically call `minimax_code` for implementation tasks. You can also prompt it directly:

> "Use minimax_code to implement the authentication endpoint"

## Requirements

- Python 3.10+
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `claude` CLI installed and authenticated
```

- [ ] **Step 2: Add minimax MCP server to Claude Code settings**

Read `~/.claude/settings.json`, then add the `mcpServers` block. The final result should include:

```json
{
  "mcpServers": {
    "minimax": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/E10Feng/minimax-mcp", "minimax-mcp"]
    }
  }
}
```

Note: `uvx` inherits env vars from the parent process, so `MINIMAX_API_KEY` will be available automatically.

- [ ] **Step 3: Commit**

```bash
cd ~/minimax-mcp
git add README.md
git commit -m "docs: add README with setup instructions"
```

---

### Task 4: Create GitHub repo and push

**Files:** None (git operations only)

- [ ] **Step 1: Create the GitHub repo**

```bash
gh repo create E10Feng/minimax-mcp --public --description "MCP server delegating code implementation to Minimax via Claude Code subprocess"
```

- [ ] **Step 2: Add remote and push**

```bash
cd ~/minimax-mcp
git remote add origin https://github.com/E10Feng/minimax-mcp.git
git push -u origin main
```

- [ ] **Step 3: Verify installation works via uvx**

```bash
MINIMAX_API_KEY=test uvx --from git+https://github.com/E10Feng/minimax-mcp minimax-mcp --help 2>&1 | head -5
```

Expected: Server starts (may show MCP protocol output or help text). No "command not found" errors.

- [ ] **Step 4: Reload Claude Code MCP servers**

In Claude Code terminal: `/mcp` to verify `minimax` server appears in the list.

---

## Self-Review Notes

- `_run_minimax_subagent` is a pure function (no side effects on `app` state) — easy to test independently ✓
- API key validated at call time (not startup) to allow server to start even without key ✓
- All error cases covered: timeout, missing CLI, non-zero exit code, JSON parse failure ✓
- `--output-format json` flag — if this flag isn't supported by the installed `claude` version, `json.JSONDecodeError` is caught and raw stdout is returned gracefully ✓
- README covers all setup steps with exact commands ✓
