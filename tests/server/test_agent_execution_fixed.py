import pytest
import sys
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from opentelemetry import trace

sys.modules['openlit'] = MagicMock()

from agentuity.server import run_agent  # noqa: E402
from agentuity.server.request import AgentRequest  # noqa: E402
from agentuity.server.response import AgentResponse  # noqa: E402
from agentuity.server.data import Data  # noqa: E402


class TestAgentExecution:
    """Test suite for agent execution functionality."""
    
    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer for testing."""
        tracer = MagicMock(spec=trace.Tracer)
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span
        return tracer
    
    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        agent = {
            "id": "test_agent",
            "name": "Test Agent",
            "run": AsyncMock()
        }
        agent["run"].return_value = AgentResponse({}, MagicMock(), {}, 3000)
        return agent
    
    @pytest.fixture
    def mock_request_data(self):
        """Create mock request data for testing."""
        return {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": base64.b64encode(b"Hello, world!").decode("utf-8"),
            "metadata": {"key": "value"}
        }
    
    @pytest.fixture
    def mock_agents_by_id(self):
        """Create a mock agents_by_id dictionary."""
        return {
            "test_agent": {
                "id": "test_agent",
                "name": "Test Agent",
                "run": AsyncMock(return_value=AgentResponse({}, MagicMock(), {}, 3000))
            }
        }
    
    @pytest.mark.asyncio
    async def test_run_agent_success(self, mock_tracer, mock_agent, mock_request_data, mock_agents_by_id):
        """Test successful agent execution."""
        response = AgentResponse({}, mock_tracer, mock_agents_by_id, 3000)
        response.text("Test response")
        mock_agent["run"].return_value = response
        
        result = await run_agent(mock_tracer, "test_agent", mock_agent, mock_request_data, mock_agents_by_id)
        
        mock_agent["run"].assert_called_once()
        
        assert result.content_type == "text/plain"
        assert result.payload is not None
    
    @pytest.mark.asyncio
    async def test_run_agent_with_json_request(self, mock_tracer, mock_agent, mock_agents_by_id):
        """Test agent execution with JSON request."""
        json_data = {"message": "Hello, world!"}
        request_data = {
            "contentType": "application/json",
            "trigger": "manual",
            "payload": base64.b64encode(json.dumps(json_data).encode()).decode(),
            "metadata": {"key": "value"}
        }
        
        response = AgentResponse({}, mock_tracer, mock_agents_by_id, 3000)
        response.text("Test response")
        mock_agent["run"].return_value = response
        
        result = await run_agent(mock_tracer, "test_agent", mock_agent, request_data, mock_agents_by_id)
        
        mock_agent["run"].assert_called_once()
        
        assert result.content_type == "text/plain"
        assert result.payload is not None
    
    @pytest.mark.asyncio
    async def test_run_agent_with_binary_request(self, mock_tracer, mock_agent, mock_agents_by_id):
        """Test agent execution with binary request."""
        binary_data = b"\x00\x01\x02\x03"
        request_data = {
            "contentType": "application/octet-stream",
            "trigger": "manual",
            "payload": base64.b64encode(binary_data).decode(),
            "metadata": {"key": "value"}
        }
        
        response = AgentResponse({}, mock_tracer, mock_agents_by_id, 3000)
        response.text("Test response")
        mock_agent["run"].return_value = response
        
        result = await run_agent(mock_tracer, "test_agent", mock_agent, request_data, mock_agents_by_id)
        
        mock_agent["run"].assert_called_once()
        
        assert result.content_type == "text/plain"
        assert result.payload is not None
    
    @pytest.mark.asyncio
    async def test_run_agent_with_json_response(self, mock_tracer, mock_agents_by_id):
        """Test agent execution with JSON response."""
        json_response = {"message": "Hello from agent!"}
        
        async def mock_run(request, response, context):
            return response.json(json_response)
        
        agent = {
            "id": "test_agent",
            "name": "Test Agent",
            "run": mock_run
        }
        
        request_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": base64.b64encode(b"Hello, world!").decode(),
            "metadata": {"key": "value"}
        }
        
        result = await run_agent(mock_tracer, "test_agent", agent, request_data, mock_agents_by_id)
        
        assert result.content_type == "application/json"
        assert result.payload is not None
        
        decoded_payload = base64.b64decode(result.payload).decode()
        assert json.loads(decoded_payload) == json_response
    
    @pytest.mark.asyncio
    async def test_run_agent_with_error(self, mock_tracer, mock_agents_by_id):
        """Test agent execution when an error occurs."""
        async def mock_run(request, response, context):
            raise ValueError("Test error")
        
        agent = {
            "id": "test_agent",
            "name": "Test Agent",
            "run": mock_run
        }
        
        request_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": base64.b64encode(b"Hello, world!").decode(),
            "metadata": {"key": "value"}
        }
        
        with pytest.raises(ValueError, match="Test error"):
            await run_agent(mock_tracer, "test_agent", agent, request_data, mock_agents_by_id)
    
    @pytest.mark.asyncio
    async def test_run_agent_with_streaming_response(self, mock_tracer, mock_agents_by_id):
        """Test agent execution with streaming response."""
        stream_data = ["chunk1", "chunk2", "chunk3"]
        
        async def mock_run(request, response, context):
            return response.stream(iter(stream_data))
        
        agent = {
            "id": "test_agent",
            "name": "Test Agent",
            "run": mock_run
        }
        
        request_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": base64.b64encode(b"Hello, world!").decode(),
            "metadata": {"key": "value"}
        }
        
        result = await run_agent(mock_tracer, "test_agent", agent, request_data, mock_agents_by_id)
        
        assert result.is_stream is True
        assert result.content_type == "text/plain"
        
        chunks = []
        for chunk in result:
            chunks.append(chunk)
        
        assert chunks == stream_data
