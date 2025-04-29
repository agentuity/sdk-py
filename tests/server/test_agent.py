import pytest
import sys
import json
import base64
from unittest.mock import MagicMock, AsyncMock
import httpx
from opentelemetry import trace

sys.modules["openlit"] = MagicMock()

from agentuity.server.agent import RemoteAgentResponse, RemoteAgent  # noqa: E402
from agentuity.server.config import AgentConfig  # noqa: E402
from agentuity.server.data import Data  # noqa: E402


class TestRemoteAgentResponse:
    """Test suite for the RemoteAgentResponse class."""

    def test_init(self):
        """Test initialization of RemoteAgentResponse."""
        data = {
            "contentType": "text/plain",
            "payload": base64.b64encode(b"Hello, world!").decode("utf-8"),
            "metadata": {"key": "value"},
        }

        response = RemoteAgentResponse(data)

        assert isinstance(response.data, Data)
        assert response.contentType == "text/plain"
        assert response.metadata == {"key": "value"}

    def test_init_default_values(self):
        """Test initialization with default values."""
        data = {"payload": base64.b64encode(b"Hello, world!").decode("utf-8")}

        response = RemoteAgentResponse(data)

        assert response.contentType == "text/plain"
        assert response.metadata == {}


class TestRemoteAgent:
    """Test suite for the RemoteAgent class."""

    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer for testing."""
        tracer = MagicMock(spec=trace.Tracer)
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span
        return tracer

    @pytest.fixture
    def agent_config(self):
        """Create an AgentConfig for testing."""
        return AgentConfig(
            {"id": "test_agent", "name": "Test Agent", "filename": "/path/to/agent.py"}
        )

    @pytest.fixture
    def remote_agent(self, agent_config, mock_tracer):
        """Create a RemoteAgent instance for testing."""
        return RemoteAgent(agentconfig=agent_config, port=3000, tracer=mock_tracer)

    def test_init(self, remote_agent, agent_config, mock_tracer):
        """Test initialization of RemoteAgent."""
        assert remote_agent.agentconfig == agent_config
        assert remote_agent._port == 3000
        assert remote_agent._tracer == mock_tracer

    def test_str(self, remote_agent, agent_config):
        """Test string representation of RemoteAgent."""
        assert str(remote_agent) == f"RemoteAgent(agentconfig={agent_config})"

    @pytest.mark.asyncio
    async def test_run_with_string_data(self, remote_agent, mock_tracer, monkeypatch):
        """Test running a remote agent with string data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "contentType": "text/plain",
            "payload": base64.b64encode(b"Response from agent").decode("utf-8"),
            "metadata": {"key": "value"},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_async_client = MagicMock(return_value=mock_client)
        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)

        result = await remote_agent.run("Hello, world!")

        assert isinstance(result, RemoteAgentResponse)
        assert result.contentType == "text/plain"
        assert result.data.text == "Response from agent"
        assert result.metadata == {"key": "value"}

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args

        assert args[0] == "http://127.0.0.1:3000/test_agent"
        assert kwargs["headers"] is not None

        payload = kwargs["json"]
        assert payload["trigger"] == "agent"
        assert payload["contentType"] == "text/plain"
        assert "payload" in payload

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("remote.agentId", "test_agent")
        span.set_attribute.assert_any_call("remote.agentName", "Test Agent")
        span.set_attribute.assert_any_call("scope", "local")
        span.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_json_data(self, remote_agent, mock_tracer, monkeypatch):
        """Test running a remote agent with JSON data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "contentType": "application/json",
            "payload": base64.b64encode(
                json.dumps({"result": "success"}).encode()
            ).decode("utf-8"),
            "metadata": {"key": "value"},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_async_client = MagicMock(return_value=mock_client)
        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)

        json_data = {"message": "Hello, world!"}
        result = await remote_agent.run(json_data, content_type="application/json")

        assert isinstance(result, RemoteAgentResponse)
        assert result.contentType == "application/json"
        assert result.data.json == {"result": "success"}

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args

        assert kwargs["json"]["contentType"] == "application/json"

    @pytest.mark.asyncio
    async def test_run_with_binary_data(self, remote_agent, mock_tracer, monkeypatch):
        """Test running a remote agent with binary data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "contentType": "application/octet-stream",
            "payload": base64.b64encode(b"Binary response").decode("utf-8"),
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_async_client = MagicMock(return_value=mock_client)
        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)

        binary_data = b"Binary data"
        result = await remote_agent.run(
            binary_data, content_type="application/octet-stream"
        )

        assert isinstance(result, RemoteAgentResponse)
        assert result.contentType == "application/octet-stream"
        assert result.data.binary == b"Binary response"

        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_metadata(self, remote_agent, mock_tracer, monkeypatch):
        """Test running a remote agent with metadata."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "contentType": "text/plain",
            "payload": base64.b64encode(b"Response with metadata").decode("utf-8"),
            "metadata": {"response_key": "response_value"},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_async_client = MagicMock(return_value=mock_client)
        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)

        metadata = {"request_key": "request_value"}
        result = await remote_agent.run("Hello", metadata=metadata)

        assert isinstance(result, RemoteAgentResponse)
        assert result.metadata == {"response_key": "response_value"}

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args

        assert kwargs["json"]["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_run_error(self, remote_agent, mock_tracer, monkeypatch):
        """Test error handling during remote agent execution."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.content = b"Internal server error"
        mock_response.text = "Internal server error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_async_client = MagicMock(return_value=mock_client)
        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)

        with pytest.raises(Exception) as excinfo:
            await remote_agent.run("Hello, world!")

        assert "Internal server error" in str(excinfo.value)

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.record_exception.assert_called_once()
        span.set_status.assert_called_once()
