import pytest
import sys
import json
from unittest.mock import patch, MagicMock
import yaml

sys.modules["openlit"] = MagicMock()

from agentuity.server import load_config, load_agents, autostart  # noqa: E402


class TestServerConfig:
    """Test suite for server configuration functions."""

    def test_load_config_agentuity_yaml(self, tmp_path):
        """Test loading configuration from agentuity.yaml."""
        config_path = tmp_path / "agentuity.yaml"
        config_data = {
            "name": "test_agent",
            "version": "1.0.0",
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "filename": str(tmp_path / "agents" / "test_agent" / "agent.py"),
                }
            ],
        }
        config_path.write_text(yaml.dump(config_data))

        agent_dir = tmp_path / "agents" / "test_agent"
        agent_dir.mkdir(parents=True)

        agent_file = agent_dir / "agent.py"
        agent_file.write_text(
            "def run(request, response, context):\n    return response.text('Hello')"
        )

        with (
            patch("os.getcwd", return_value=str(tmp_path)),
            patch("os.path.exists") as mock_exists,
            patch("yaml.safe_load", return_value=config_data),
        ):

            def exists_side_effect(path):
                if ".agentuity/config.json" in path:
                    return False
                elif "agentuity.yaml" in path:
                    return True
                return False

            mock_exists.side_effect = exists_side_effect

            result = load_config()

            assert result is not None
            assert result["environment"] == "development"
            assert result["app"]["name"] == "test_agent"
            assert result["app"]["version"] == "dev"

    def test_load_config_dot_agentuity(self, tmp_path):
        """Test loading configuration from .agentuity/config.json."""
        config_dir = tmp_path / ".agentuity"
        config_dir.mkdir()

        config_path = config_dir / "config.json"
        config_data = {
            "environment": "development",
            "cli_version": "1.0.0",
            "app": {"name": "test_app", "version": "1.0.0"},
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "filename": str(tmp_path / "agents" / "test_agent" / "agent.py"),
                }
            ],
        }
        config_path.write_text(json.dumps(config_data))

        agent_dir = tmp_path / "agents" / "test_agent"
        agent_dir.mkdir(parents=True)

        agent_file = agent_dir / "agent.py"
        agent_file.write_text(
            "def run(request, response, context):\n    return response.text('Hello')"
        )

        with (
            patch("os.getcwd", return_value=str(tmp_path)),
            patch("os.path.exists", side_effect=lambda path: path == str(config_path)),
            patch("builtins.open", create=True) as mock_open,
        ):
            mock_open.return_value.__enter__.return_value = config_path.open()

            result = load_config()

            assert result is not None
            assert result["environment"] == "development"
            assert result["cli_version"] == "1.0.0"
            assert result["app"]["name"] == "test_app"
            assert result["app"]["version"] == "1.0.0"
            assert "agents" in result

    def test_load_agents_success(self, tmp_path):
        """Test successful loading of agents."""
        agent_dir = tmp_path / "agents" / "test_agent"
        agent_dir.mkdir(parents=True)

        agent_file = agent_dir / "agent.py"
        agent_file.write_text(
            "def run(request, response, context):\n    return response.text('Hello')"
        )

        config_data = {
            "environment": "development",
            "cli_version": "1.0.0",
            "app": {"name": "test_app", "version": "1.0.0"},
            "agents": [
                {"id": "test_agent", "name": "Test Agent", "filename": str(agent_file)}
            ],
        }

        with (
            patch("agentuity.server.load_agent_module") as mock_load_agent_module,
            patch("agentuity.server.logger.info"),
            patch("agentuity.server.logger.debug"),
            patch("os.path.exists", return_value=True),
        ):
            mock_load_agent_module.return_value = {
                "id": "test_agent",
                "name": "Test Agent",
                "run": lambda request, response, context: response.text("Hello"),
            }

            result = load_agents(config_data)

            assert result is not None
            assert "test_agent" in result
            assert result["test_agent"]["id"] == "test_agent"
            assert result["test_agent"]["name"] == "Test Agent"
            assert callable(result["test_agent"]["run"])

            mock_load_agent_module.assert_called_once_with(
                agent_id="test_agent", name="Test Agent", filename=str(agent_file)
            )

    def test_load_agents_file_not_found(self):
        """Test loading agents when the agent file is not found."""
        config_data = {
            "environment": "development",
            "cli_version": "1.0.0",
            "app": {"name": "test_app", "version": "1.0.0"},
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "filename": "/non/existent/path/agent.py",
                }
            ],
        }

        with (
            patch("agentuity.server.logger.error") as mock_logger_error,
            patch("os.path.exists", return_value=False),
            pytest.raises(SystemExit),
        ):
            load_agents(config_data)

            mock_logger_error.assert_called_once()

    def test_load_agents_json_error(self):
        """Test loading agents with a JSON decode error."""
        config_data = {
            "environment": "development",
            "cli_version": "1.0.0",
            "app": {"name": "test_app", "version": "1.0.0"},
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "filename": "/path/to/agent.py",
                }
            ],
        }

        with (
            patch("agentuity.server.load_agent_module") as mock_load_agent_module,
            patch("agentuity.server.logger.error") as mock_logger_error,
            patch("os.path.exists", return_value=True),
            pytest.raises(SystemExit),
        ):
            mock_load_agent_module.side_effect = json.JSONDecodeError(
                "Invalid JSON", "", 0
            )

            load_agents(config_data)

            mock_logger_error.assert_called_once()

    def test_autostart(self):
        """Test the autostart function."""
        with (
            patch("agentuity.server.asyncio.new_event_loop") as mock_new_event_loop,
            patch("agentuity.server.asyncio.set_event_loop") as mock_set_event_loop,
            patch("agentuity.server.logger.setLevel") as mock_set_level,
            patch("agentuity.server.load_config") as mock_load_config,
            patch("agentuity.server.init") as mock_init,
            patch("agentuity.server.instrument") as mock_instrument,
            patch("agentuity.server.load_agents") as mock_load_agents,
            patch("agentuity.server.web.Application") as mock_application,
            patch("agentuity.server.web.run_app") as mock_run_app,
            patch("agentuity.server.logger.info") as mock_logger_info,
            patch("agentuity.server.logger.addHandler") as mock_add_handler,
        ):
            mock_loop = MagicMock()
            mock_new_event_loop.return_value = mock_loop

            mock_config = {
                "environment": "development",
                "cli_version": "1.0.0",
                "app": {"name": "test_app", "version": "1.0.0"},
                "agents": [],
            }
            mock_load_config.return_value = mock_config

            mock_log_handler = MagicMock()
            mock_init.return_value = mock_log_handler

            mock_agents = {"test_agent": {"id": "test_agent", "name": "Test Agent"}}
            mock_load_agents.return_value = mock_agents

            mock_app = MagicMock()
            mock_application.return_value = mock_app

            mock_callback = MagicMock()

            autostart(mock_callback)

            mock_new_event_loop.assert_called_once()
            mock_set_event_loop.assert_called_once_with(mock_loop)
            mock_set_level.assert_called_once()
            mock_load_config.assert_called_once()
            mock_init.assert_called_once()
            mock_instrument.assert_called_once()
            mock_callback.assert_called_once()
            mock_load_agents.assert_called_once_with(mock_config)
            mock_add_handler.assert_called_once_with(mock_log_handler)
            mock_application.assert_called_once()

            mock_app.__setitem__.assert_called_once_with("agents_by_id", mock_agents)

            assert mock_app.router.add_get.call_count == 4
            assert mock_app.router.add_post.call_count == 2

            mock_run_app.assert_called_once()
            mock_logger_info.assert_called()
