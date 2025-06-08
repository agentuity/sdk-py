import pytest
import sys
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock
import httpx
from opentelemetry import trace

sys.modules["openlit"] = MagicMock()

from agentuity.server.agent import RemoteAgentResponse, RemoteAgent  # noqa: E402
from agentuity.server.data import Data  # noqa: E402


class TestRemoteAgentResponse:
    """Test suite for the RemoteAgentResponse class."""

    def test_init(self):
        """Test initialization of RemoteAgentResponse."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        data = Data("text/plain", reader)

        headers = {"x-agentuity-key": "value"}

        response = RemoteAgentResponse(data, headers)

        assert response.data == data
        assert response.metadata == {"key": "value"}

    def test_init_default_values(self):
        """Test initialization with default values."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        data = Data("text/plain", reader)

        response = RemoteAgentResponse(data)

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
        return {
            "id": "test_agent",
            "name": "Test Agent",
            "filename": "/path/to/agent.py",
            "url": "http://127.0.0.1:3000/test_agent",
            "authorization": "test_auth_token",
            "orgId": "test_org",
            "projectId": "test_project",
            "transactionId": "test_transaction",
        }

    @pytest.fixture
    def remote_agent(self, agent_config, mock_tracer):
        """Create a RemoteAgent instance for testing."""
        return RemoteAgent(agentconfig=agent_config, port=3000, tracer=mock_tracer)

    def test_init(self, remote_agent, agent_config, mock_tracer):
        """Test initialization of RemoteAgent."""
        assert remote_agent.agentconfig == agent_config
        assert remote_agent.port == 3000
        assert remote_agent.tracer == mock_tracer

    def test_str(self, remote_agent, agent_config):
        """Test string representation of RemoteAgent."""
        assert str(remote_agent) == f"RemoteAgent(agent={agent_config['id']})"

    @pytest.mark.asyncio
    async def test_run_with_string_data(self, remote_agent, mock_tracer, monkeypatch):
        """Test running a remote agent with string data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/plain",
            "x-agentuity-key": "value",
        }

        async def mock_aiter_bytes():
            yield b"Response from agent"

        mock_response.aiter_bytes = mock_aiter_bytes

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_stream_reader = asyncio.StreamReader()
        mock_stream_reader.feed_data(b"Response from agent")
        mock_stream_reader.feed_eof()

        async def mock_create_stream_reader(response):
            return mock_stream_reader

        monkeypatch.setattr(
            "agentuity.server.agent.create_stream_reader", mock_create_stream_reader
        )
        monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()
        data = Data("text/plain", reader)

        async def mock_stream():
            return reader

        data.stream = mock_stream

        result = await remote_agent.run(data)

        assert isinstance(result, RemoteAgentResponse)
        assert result.data.content_type == "text/plain"
        text = await result.data.text()
        assert text == "Response from agent"
        assert result.metadata == {"key": "value"}

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args

        assert args[0] == "http://127.0.0.1:3000/test_agent"
        assert kwargs["headers"] is not None

        assert "content" in kwargs

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("@agentuity/agentId", "test_agent")
        span.set_attribute.assert_any_call("@agentuity/agentName", "Test Agent")
        span.set_attribute.assert_any_call("@agentuity/scope", "remote")
        span.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_json_data(self, remote_agent, mock_tracer, monkeypatch):
        """Test running a remote agent with JSON data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "application/json",
            "x-agentuity-key": "value",
        }

        async def mock_aiter_bytes():
            yield json.dumps({"result": "success"}).encode()

        mock_response.aiter_bytes = mock_aiter_bytes

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_stream_reader = asyncio.StreamReader()
        mock_stream_reader.feed_data(json.dumps({"result": "success"}).encode())
        mock_stream_reader.feed_eof()

        async def mock_create_stream_reader(response):
            return mock_stream_reader

        monkeypatch.setattr(
            "agentuity.server.agent.create_stream_reader", mock_create_stream_reader
        )
        monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

        json_data = {"message": "Hello, world!"}
        reader = asyncio.StreamReader()
        reader.feed_data(json.dumps(json_data).encode())
        reader.feed_eof()
        data = Data("application/json", reader)

        async def mock_stream():
            return reader

        data.stream = mock_stream

        result = await remote_agent.run(data)

        assert isinstance(result, RemoteAgentResponse)
        assert result.data.content_type == "application/json"
        json_data = await result.data.json()
        assert json_data == {"result": "success"}

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args

        assert "content" in kwargs

    @pytest.mark.asyncio
    async def test_run_with_binary_data(self, remote_agent, mock_tracer, monkeypatch):
        """Test running a remote agent with binary data."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/octet-stream"}

        async def mock_aiter_bytes():
            yield b"Binary response"

        mock_response.aiter_bytes = mock_aiter_bytes

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_stream_reader = asyncio.StreamReader()
        mock_stream_reader.feed_data(b"Binary response")
        mock_stream_reader.feed_eof()

        async def mock_create_stream_reader(response):
            return mock_stream_reader

        monkeypatch.setattr(
            "agentuity.server.agent.create_stream_reader", mock_create_stream_reader
        )
        monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

        binary_data = b"Binary data"
        reader = asyncio.StreamReader()
        reader.feed_data(binary_data)
        reader.feed_eof()
        data = Data("application/octet-stream", reader)

        async def mock_stream():
            return reader

        data.stream = mock_stream

        result = await remote_agent.run(data)

        assert isinstance(result, RemoteAgentResponse)
        assert result.data.content_type == "application/octet-stream"
        binary_data = await result.data.binary()
        assert binary_data == b"Binary response"

        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_metadata(self, remote_agent, mock_tracer, monkeypatch):
        """Test running a remote agent with metadata."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {
            "content-type": "text/plain",
            "x-agentuity-response_key": "response_value",
        }

        async def mock_aiter_bytes():
            yield b"Response with metadata"

        mock_response.aiter_bytes = mock_aiter_bytes

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_stream_reader = asyncio.StreamReader()
        mock_stream_reader.feed_data(b"Response with metadata")
        mock_stream_reader.feed_eof()

        async def mock_create_stream_reader(response):
            return mock_stream_reader

        monkeypatch.setattr(
            "agentuity.server.agent.create_stream_reader", mock_create_stream_reader
        )
        monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello")
        reader.feed_eof()
        data = Data("text/plain", reader)

        async def mock_stream():
            return mock_stream_reader

        data.stream = mock_stream

        metadata = {"request_key": "request_value"}
        result = await remote_agent.run(data, metadata=metadata)

        assert isinstance(result, RemoteAgentResponse)
        assert result.metadata == {"response_key": "response_value"}

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args

        assert "x-agentuity-metadata" in kwargs["headers"]
        metadata_json = json.loads(kwargs["headers"]["x-agentuity-metadata"])
        assert "request_key" in metadata_json
        assert metadata_json["request_key"] == "request_value"

    @pytest.mark.asyncio
    async def test_run_error(self, remote_agent, mock_tracer, monkeypatch):
        """Test error handling during remote agent execution."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.content = b"Internal server error"
        mock_response.text = "Internal server error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_async_client = MagicMock(return_value=mock_client)
        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client)

        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()
        data = Data("text/plain", reader)

        async def mock_stream():
            return reader

        data.stream = mock_stream

        with pytest.raises(Exception) as excinfo:
            await remote_agent.run(data)

        assert "Internal server error" in str(excinfo.value)

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.record_exception.assert_called_once()
        span.set_status.assert_called_once()
