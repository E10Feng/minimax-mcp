# Minimax MCP Server — Design Spec

**Date:** 2026-04-16  
**Status:** Approved

## Problem

Ethan hits Anthropic usage limits during heavy software development sessions. Claude (Anthropic) handles planning and chatting well, but bulk code implementation consumes credits quickly. Minimax is available at ~$10/month and has already been integrated with Claude Code via `ANTHROPIC_BASE_URL`.

## Goal

Build a portable MCP server that lets Claude (Anthropic) delegate all coding implementation work to a Minimax-backed Claude Code subprocess. The Minimax subagent has full tool access and superpowers skills, runs autonomously, and returns results to the main session.

## Architecture

```
User ←→ Claude (Anthropic) [planning, chatting]
              ↓ tool call: minimax_code(task, context)
         MCP Server (Python)
              ↓ subprocess.run with env override
         claude -p "<task>" [ANTHROPIC_BASE_URL=minimax]
              ↓
         Minimax API (via Anthropic-compatible endpoint)
```

**Transport:** stdio (Claude Code spawns the MCP server process)  
**Language:** Python  
**Distribution:** runnable via `uvx` — no installation required on any machine

## Tool Interface

### `minimax_code`

```
minimax_code(
  task: str,     # Full description of what to implement
  context: str   # Optional: relevant file contents, prior decisions, constraints
) → str          # Subagent's output (code, explanation, confirmation)
```

**Behavior:**
1. Receives `task` and optional `context` from the main Claude session
2. Builds a prompt combining the task and context
3. Spawns `claude -p "<prompt>" --output-format json` with modified environment
4. Returns the subagent's output to the main Claude session

**Environment override for subprocess:**
```
ANTHROPIC_BASE_URL = https://api.minimax.io
ANTHROPIC_API_KEY  = $MINIMAX_API_KEY  (from MCP server env)
```

The main Claude session's environment is not affected — override is scoped to the child process only.

## Configuration

**Per machine (one-time setup):**
```bash
export MINIMAX_API_KEY=<your_minimax_api_key>
```

Add to shell profile (`~/.zshrc` or `~/.bashrc`) for persistence.

**Claude Code settings.json:**
```json
{
  "mcpServers": {
    "minimax": {
      "command": "uvx",
      "args": ["minimax-mcp"],
      "env": {
        "MINIMAX_API_KEY": "${MINIMAX_API_KEY}"
      }
    }
  }
}
```

## Repo Structure

```
minimax-mcp/
  server.py          # MCP server — single file
  pyproject.toml     # Package metadata and dependencies (mcp, uv)
  README.md          # Setup instructions
  docs/
    superpowers/
      specs/
        2026-04-16-minimax-mcp-design.md  # This file
```

## Error Handling

- Missing `MINIMAX_API_KEY`: server raises clear error at startup, not at call time
- Subprocess fails: return error message to Claude with subprocess stderr
- Timeout: subprocess runs with 5-minute timeout; returns timeout error if exceeded
- `claude` CLI not found: return actionable error message ("ensure `claude` is installed and in PATH")

## Testing

- Manual integration test: call `minimax_code` with a simple task ("write a hello world function") and verify output
- Verify environment isolation: confirm main process `ANTHROPIC_BASE_URL` is unaffected after a call
- Verify error handling: call without `MINIMAX_API_KEY` set, confirm clear error

## Non-Goals

- Web UI or monitoring dashboard
- Multiple Minimax model selection (use API default)
- Streaming output (return when complete)
- Usage tracking or cost estimation
