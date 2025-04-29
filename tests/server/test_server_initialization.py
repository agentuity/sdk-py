import pytest
import sys
import os
import yaml
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

sys.modules["openlit"] = MagicMock()

from agentuity.server import (  # noqa: E402
    load_agents,
    load_agent_module,
    autostart,
)


class TestServerInitialization:
    """Test suite for server initialization and agent loading."""

    @pytest.fixture
    def mock_yaml_config(self):
        """Create a mock YAML configuration file."""
        config = {
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "module": "test_agent_module.py",
                },
                {
                    "id": "another_agent",
                    "name": "Another Agent",
                    "module": "another_agent_module.py",
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name

        yield config_path

        os.unlink(config_path)

    @pytest.fixture
    def mock_agent_module(self):
        """Create a mock agent module file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                "async def run(request, response, context):\n    return response.text('Hello from test agent')"
            )
            module_path = f.name

        yield module_path

        os.unlink(module_path)

    def test_load_agent_module(self, mock_agent_module):
        """Test loading an agent module."""
        with patch("agentuity.server.logger.debug"):
            agent = load_agent_module("test_agent", "Test Agent", mock_agent_module)

            assert agent["id"] == "test_agent"
            assert agent["name"] == "Test Agent"
            assert callable(agent["run"])

    def test_load_agent_module_missing_run(self):
        """Test loading an agent module without a run function."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# This module has no run function")
            module_path = f.name

        try:
            with (
                patch("agentuity.server.logger.debug"),
                pytest.raises(AttributeError, match="does not have a run function"),
            ):
                load_agent_module("test_agent", "Test Agent", module_path)
        finally:
            os.unlink(module_path)

    def test_load_agents(self, mock_yaml_config, mock_agent_module):
        """Test loading agents from a YAML configuration file."""
        with (
            patch("agentuity.server.logger.debug"),
            patch("agentuity.server.os.path.exists", return_value=True),
            patch("agentuity.server.os.path.isfile", return_value=True),
            patch("agentuity.server.load_agent_module") as mock_load_agent,
        ):
            mock_load_agent.return_value = {
                "id": "test_agent",
                "name": "Test Agent",
                "run": AsyncMock(),
            }

            with patch("agentuity.server.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = open(
                    mock_yaml_config
                ).read()

                mock_config_data = {
                    "agents": [
                        {
                            "id": "test_agent",
                            "name": "Test Agent",
                            "filename": "test_agent_module.py",
                        },
                        {
                            "id": "another_agent",
                            "name": "Another Agent",
                            "filename": "another_agent_module.py",
                        },
                    ]
                }
                agents = load_agents(mock_config_data)

                assert "test_agent" in agents
                assert "another_agent" in agents
                assert mock_load_agent.call_count == 2

    def test_load_agents_no_config(self):
        """Test loading agents when no configuration file exists."""
        with (
            patch("agentuity.server.logger.debug"),
            patch("agentuity.server.os.path.exists", return_value=False),
            patch("agentuity.server.logger.warning"),
        ):
            mock_config_data = {"agents": []}
            agents = load_agents(mock_config_data)

            assert agents == {}

    def test_load_agents_invalid_yaml(self):
        """Test loading agents with an invalid YAML configuration."""
        with (
            patch("agentuity.server.logger.debug"),
            patch("agentuity.server.os.path.exists", return_value=True),
            patch("agentuity.server.os.path.isfile", return_value=True),
            patch("agentuity.server.open", create=True) as mock_open,
            patch("agentuity.server.logger.error"),
        ):
            mock_open.return_value.__enter__.return_value.read.return_value = (
                "invalid: yaml: :"
            )

            mock_config_data = {"agents": []}
            agents = load_agents(mock_config_data)

            assert agents == {}

    def test_autostart(self):
        """Test the autostart function."""
        with (
            patch("agentuity.server.web.Application") as mock_app_class,
            patch("agentuity.server.web.run_app") as mock_run_app,
            patch("agentuity.server.instrument") as mock_instrument,
            patch("agentuity.otel.init"),
            patch("agentuity.server.load_config") as mock_load_config,
            patch("agentuity.server.load_agents") as mock_load_agents,
            patch("agentuity.server.logger.info"),
        ):
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            mock_config_data = {
                "cli_version": "1.0.0",
                "environment": "test",
                "app": {"name": "test_app", "version": "1.0.0"},
                "agents": [],
            }
            mock_load_config.return_value = mock_config_data
            mock_load_agents.return_value = {}

            autostart()

            mock_instrument.assert_called_once()
            mock_app_class.assert_called_once()
            mock_run_app.assert_called_once_with(
                mock_app, host="127.0.0.1", port=3500, access_log=None
            )

    def test_autostart_with_custom_port(self):
        """Test the autostart function with a custom port."""
        with (
            patch("agentuity.server.web.Application") as mock_app_class,
            patch("agentuity.server.web.run_app") as mock_run_app,
            patch("agentuity.server.instrument"),
            patch("agentuity.otel.init"),
            patch("agentuity.server.load_config") as mock_load_config,
            patch("agentuity.server.load_agents") as mock_load_agents,
            patch("agentuity.server.logger.info"),
        ):
            mock_app = MagicMock()
            mock_app_class.return_value = mock_app

            mock_config_data = {
                "cli_version": "1.0.0",
                "environment": "test",
                "app": {"name": "test_app", "version": "1.0.0"},
                "agents": [],
            }
            mock_load_config.return_value = mock_config_data
            mock_load_agents.return_value = {}

            with patch("agentuity.server.port", 5000):
                autostart()

            mock_run_app.assert_called_once_with(
                mock_app, host="127.0.0.1", port=5000, access_log=None
            )
