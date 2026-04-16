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
