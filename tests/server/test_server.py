import pytest
import os
import tempfile
import sys
from unittest.mock import patch, MagicMock

sys.modules["openlit"] = MagicMock()

from agentuity.server import load_agent_module, inject_trace_context  # noqa: E402


class TestServerFunctions:
    """Test suite for server initialization and utility functions."""

    def test_inject_trace_context(self):
        """Test inject_trace_context function."""
        headers = {}
        with patch("agentuity.server.inject") as mock_inject:
            inject_trace_context(headers)
            mock_inject.assert_called_once_with(headers)

    def test_inject_trace_context_error(self):
        """Test inject_trace_context handles errors."""
        headers = {}
        with (
            patch("agentuity.server.inject", side_effect=Exception("Test error")),
            patch("agentuity.server.logger.error") as mock_error,
        ):
            inject_trace_context(headers)
            mock_error.assert_called_once()

    def test_load_agent_module(self):
        """Test load_agent_module function."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(
                b"def run(request, response, context): return response.text('Hello')"
            )
            module_path = f.name

        try:
            with patch("agentuity.server.logger.debug"):
                result = load_agent_module("test_agent", "Test Agent", module_path)
                assert result["id"] == "test_agent"
                assert result["name"] == "Test Agent"
                assert callable(result["run"])
        finally:
            os.unlink(module_path)

    def test_load_agent_module_missing_run(self):
        """Test load_agent_module raises AttributeError if run function is missing."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"# Empty module without run function")
            module_path = f.name

        try:
            with (
                patch("agentuity.server.logger.debug"),
                pytest.raises(AttributeError, match="does not have a run function"),
            ):
                load_agent_module("test_agent", "Test Agent", module_path)
        finally:
            os.unlink(module_path)
