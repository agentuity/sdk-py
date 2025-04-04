import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from opentelemetry import trace

sys.modules['openlit'] = MagicMock()

from agentuity.server import run_agent, load_agent_module  # noqa: E402
from agentuity.server.request import AgentRequest  # noqa: E402
from agentuity.server.response import AgentResponse  # noqa: E402


class TestAgentExecution:
    """Test suite for agent execution functions."""
    
    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer."""
        tracer = MagicMock(spec=trace.Tracer)
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span
        return tracer
    
    @pytest.fixture
    def mock_agents_by_id(self):
        """Create a mock agents_by_id dictionary."""
        return {
            "test_agent": {
                "id": "test_agent",
                "name": "Test Agent",
                "run": AsyncMock(return_value="Test response"),
            }
        }
    
    @pytest.fixture
    def mock_payload(self):
        """Create a mock request payload."""
        return {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",  # "Hello, world!" in base64
            "metadata": {"key": "value"}
        }
    
    @pytest.mark.asyncio
    async def test_run_agent_success(self, mock_tracer, mock_agents_by_id, mock_payload):
        """Test successful agent execution."""
        with patch("agentuity.server.AgentRequest") as mock_agent_request_class, \
             patch("agentuity.server.AgentResponse") as mock_agent_response_class, \
             patch("agentuity.server.AgentContext") as mock_agent_context_class, \
             patch.dict(os.environ, {"AGENTUITY_TRANSPORT_URL": "https://test.com", "AGENTUITY_API_KEY": "test_key"}):
            
            mock_agent_request = MagicMock(spec=AgentRequest)
            mock_agent_request_class.return_value = mock_agent_request
            
            mock_agent_response = MagicMock(spec=AgentResponse)
            mock_agent_response_class.return_value = mock_agent_response
            
            mock_agent_context = MagicMock()
            mock_agent_context_class.return_value = mock_agent_context
            
            agent = mock_agents_by_id["test_agent"]
            result = await run_agent(mock_tracer, "test_agent", agent, mock_payload, mock_agents_by_id)
            
            assert result == "Test response"
            
            mock_agent_request_class.assert_called_once_with(mock_payload)
            mock_agent_request.validate.assert_called_once()
            
            mock_agent_response_class.assert_called_once()
            
            mock_agent_context_class.assert_called_once()
            
            agent["run"].assert_called_once_with(
                request=mock_agent_request,
                response=mock_agent_response,
                context=mock_agent_context
            )
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_agent_exception(self, mock_tracer, mock_agents_by_id, mock_payload):
        """Test agent execution when an exception occurs."""
        with patch("agentuity.server.AgentRequest") as mock_agent_request_class, \
             patch("agentuity.server.AgentResponse") as mock_agent_response_class, \
             patch("agentuity.server.AgentContext") as mock_agent_context_class, \
             patch.dict(os.environ, {"AGENTUITY_TRANSPORT_URL": "https://test.com", "AGENTUITY_API_KEY": "test_key"}):
            
            mock_agent_request = MagicMock(spec=AgentRequest)
            mock_agent_request_class.return_value = mock_agent_request
            
            mock_agent_request.validate.side_effect = ValueError("Invalid request")
            
            mock_agent_response = MagicMock(spec=AgentResponse)
            mock_agent_response_class.return_value = mock_agent_response
            
            mock_agent_context = MagicMock()
            mock_agent_context_class.return_value = mock_agent_context
            
            agent = mock_agents_by_id["test_agent"]
            with pytest.raises(ValueError, match="Invalid request"):
                await run_agent(mock_tracer, "test_agent", agent, mock_payload, mock_agents_by_id)
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.record_exception.assert_called_once()
            span.set_status.assert_called_once()
    
    def test_load_agent_module_success(self, tmp_path):
        """Test successful loading of an agent module."""
        module_path = tmp_path / "test_agent.py"
        module_path.write_text("def run(request, response, context):\n    return response.text('Hello')")
        
        with patch("agentuity.server.logger.debug"):
            result = load_agent_module("test_agent", "Test Agent", str(module_path))
            
            assert result["id"] == "test_agent"
            assert result["name"] == "Test Agent"
            assert callable(result["run"])
    
    def test_load_agent_module_missing_run(self, tmp_path):
        """Test loading an agent module without a run function."""
        module_path = tmp_path / "test_agent.py"
        module_path.write_text("# Empty module without run function")
        
        with patch("agentuity.server.logger.debug"), \
             pytest.raises(AttributeError, match="does not have a run function"):
            load_agent_module("test_agent", "Test Agent", str(module_path))
    
    def test_load_agent_module_import_error(self, tmp_path):
        """Test loading an agent module with an import error."""
        module_path = tmp_path / "test_agent.txt"
        module_path.write_text("This is not a Python file")
        
        with patch("agentuity.server.logger.debug"), \
             pytest.raises(ImportError, match="Could not load module"):
            load_agent_module("test_agent", "Test Agent", str(module_path))
