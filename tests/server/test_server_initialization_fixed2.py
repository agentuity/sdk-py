import pytest
import sys
import os
import yaml
import json
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp.web import Application

sys.modules['openlit'] = MagicMock()

from agentuity.server import (  # noqa: E402
    load_agents,
    load_agent_module,
    autostart,
    load_config
)


class TestServerInitialization:
    """Test suite for server initialization and agent loading."""
    
    @pytest.fixture
    def mock_yaml_config(self):
        """Create a mock YAML configuration file."""
        config = {
            "name": "test-app",
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "filename": "test_agent_module.py"
                },
                {
                    "id": "another_agent",
                    "name": "Another Agent",
                    "filename": "another_agent_module.py"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_path = f.name
            
        yield config_path
        
        os.unlink(config_path)
    
    @pytest.fixture
    def mock_json_config(self):
        """Create a mock JSON configuration file."""
        config = {
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent"
                }
            ],
            "environment": "development",
            "cli_version": "1.0.0",
            "app": {
                "name": "test-app",
                "version": "1.0.0"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            config_path = f.name
            
        yield config_path
        
        os.unlink(config_path)
    
    @pytest.fixture
    def mock_agent_module(self):
        """Create a mock agent module file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("async def run(request, response, context):\n    return response.text('Hello from test agent')")
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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("# This module has no run function")
            module_path = f.name
            
        try:
            with patch("agentuity.server.logger.debug"), \
                 pytest.raises(AttributeError, match="does not have a run function"):
                load_agent_module("test_agent", "Test Agent", module_path)
        finally:
            os.unlink(module_path)
    
    def test_load_config_json(self, mock_json_config):
        """Test loading configuration from a JSON file."""
        with patch("agentuity.server.os.path.exists") as mock_exists, \
             patch("agentuity.server.os.path.join") as mock_join, \
             patch("agentuity.server.open", create=True) as mock_open:
            
            mock_exists.side_effect = [True, False]
            mock_join.return_value = mock_json_config
            mock_open.return_value.__enter__.return_value.read.return_value = open(mock_json_config).read()
            
            config_data = load_config()
            
            assert config_data is not None
            assert "environment" in config_data
            assert "app" in config_data
            assert config_data["app"]["name"] == "test-app"
    
    def test_load_config_yaml(self, mock_yaml_config):
        """Test loading configuration from a YAML file."""
        with patch("agentuity.server.os.path.exists") as mock_exists, \
             patch("agentuity.server.os.path.join") as mock_join, \
             patch("agentuity.server.open", create=True) as mock_open:
            
            mock_exists.side_effect = [False, True]
            mock_join.side_effect = ["non_existent_path", mock_yaml_config]
            mock_open.return_value.__enter__.return_value.read.return_value = open(mock_yaml_config).read()
            
            config_data = load_config()
            
            assert config_data is not None
            assert "environment" in config_data
            assert "app" in config_data
            assert config_data["app"]["name"] == "test-app"
    
    def test_load_agents_with_config(self, mock_agent_module):
        """Test loading agents with a configuration."""
        config_data = {
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "filename": mock_agent_module
                }
            ]
        }
        
        with patch("agentuity.server.logger.debug"), \
             patch("agentuity.server.os.path.exists", return_value=True), \
             patch("agentuity.server.logger.info"):
            
            agents = load_agents(config_data)
            
            assert "test_agent" in agents
            assert agents["test_agent"]["id"] == "test_agent"
            assert agents["test_agent"]["name"] == "Test Agent"
            assert callable(agents["test_agent"]["run"])
    
    def test_load_agents_missing_file(self):
        """Test loading agents when a file is missing."""
        config_data = {
            "agents": [
                {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "filename": "/non/existent/path.py"
                }
            ]
        }
        
        with patch("agentuity.server.logger.debug"), \
             patch("agentuity.server.os.path.exists", return_value=False), \
             patch("agentuity.server.logger.error"), \
             patch("agentuity.server.sys.exit") as mock_exit:
            
            with pytest.raises(SystemExit):
                load_agents(config_data)
            
            mock_exit.assert_called_once_with(1)
    
    def test_autostart(self):
        """Test the autostart function."""
        with patch("agentuity.server.load_config") as mock_load_config, \
             patch("agentuity.server.web.run_app"), \
             patch("agentuity.server.instrument"), \
             patch("agentuity.server.init"), \
             patch("agentuity.server.load_agents") as mock_load_agents, \
             patch("agentuity.server.web.Application") as mock_app_class, \
             patch("agentuity.server.logger.info"), \
             patch("agentuity.server.asyncio.new_event_loop"), \
             patch("agentuity.server.asyncio.set_event_loop"), \
             patch("agentuity.server.sys.exit"):
            
            config_data = {
                "cli_version": "1.0.0",
                "environment": "test",
                "app": {
                    "name": "test-app",
                    "version": "1.0.0"
                }
            }
            mock_load_config.return_value = config_data
            
            agents = {
                "test_agent": {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "run": AsyncMock()
                }
            }
            mock_load_agents.return_value = agents
            
            mock_app = MagicMock(spec=Application)
            mock_app_class.return_value = mock_app
            
            autostart()
            
            mock_load_config.assert_called_once()
            mock_load_agents.assert_called_once_with(config_data)
            mock_app_class.assert_called_once()
            
            assert mock_app.router.add_get.call_count >= 2
            assert mock_app.router.add_post.call_count >= 2
            
    
    def test_autostart_with_callback(self):
        """Test the autostart function with a callback."""
        with patch("agentuity.server.load_config") as mock_load_config, \
             patch("agentuity.server.web.run_app"), \
             patch("agentuity.server.instrument"), \
             patch("agentuity.server.init"), \
             patch("agentuity.server.load_agents") as mock_load_agents, \
             patch("agentuity.server.web.Application") as mock_app_class, \
             patch("agentuity.server.logger.info"), \
             patch("agentuity.server.asyncio.new_event_loop"), \
             patch("agentuity.server.asyncio.set_event_loop"), \
             patch("agentuity.server.sys.exit"):
            
            config_data = {
                "cli_version": "1.0.0",
                "environment": "test",
                "app": {
                    "name": "test-app",
                    "version": "1.0.0"
                }
            }
            mock_load_config.return_value = config_data
            
            agents = {
                "test_agent": {
                    "id": "test_agent",
                    "name": "Test Agent",
                    "run": AsyncMock()
                }
            }
            mock_load_agents.return_value = agents
            
            mock_app = MagicMock(spec=Application)
            mock_app_class.return_value = mock_app
            
            callback = MagicMock()
            
            autostart(callback)
            
            callback.assert_called_once()
