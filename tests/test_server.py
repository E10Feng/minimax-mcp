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
