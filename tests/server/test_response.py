import pytest
import asyncio
from unittest.mock import MagicMock
import json
import sys
from opentelemetry import trace

sys.modules["openlit"] = MagicMock()

from agentuity.server.response import AgentResponse  # noqa: E402
from agentuity.server.data import Data  # noqa: E402
from agentuity.server.context import AgentContext  # noqa: E402


class TestAgentResponse:
    """Test suite for the AgentResponse class."""

    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer for testing."""
        return MagicMock(spec=trace.Tracer)

    @pytest.fixture
    def mock_agents_by_id(self):
        """Create a mock agents_by_id dict for testing."""
        return {
            "agent_123": {
                "id": "agent_123",
                "name": "test_agent",
                "run": MagicMock(),
            }
        }

    @pytest.fixture
    def mock_context(self, mock_tracer, mock_agents_by_id):
        """Create a mock AgentContext for testing."""
        context = MagicMock(spec=AgentContext)
        context.tracer = mock_tracer
        context.agents_by_id = mock_agents_by_id
        context.port = 3500
        return context

    @pytest.fixture
    def agent_response(self, mock_context):
        """Create an AgentResponse instance for testing."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        data = Data("text/plain", reader)
        return AgentResponse(mock_context, data)

    def test_init(self, agent_response, mock_context):
        """Test initialization of AgentResponse."""
        assert agent_response.content_type == "application/octet-stream"
        assert agent_response._payload is None
        assert agent_response.metadata == {}
        assert agent_response._tracer == mock_context.tracer
        assert agent_response._context == mock_context
        assert agent_response._port == mock_context.port

    def test_text(self, agent_response):
        """Test setting a text response."""
        result = agent_response.text("Hello, world!")
        assert result == agent_response  # Should return self for chaining
        assert agent_response.content_type == "text/plain"
        assert agent_response._payload == "Hello, world!"
        assert agent_response._metadata is None

        result = agent_response.text("Hello, world!", {"key": "value"})
        assert agent_response._metadata == {"key": "value"}

    def test_json(self, agent_response):
        """Test setting a JSON response."""
        json_data = {"message": "Hello, world!"}
        result = agent_response.json(json_data)
        assert result == agent_response  # Should return self for chaining
        assert agent_response.content_type == "application/json"
        assert agent_response._payload == json.dumps(json_data)

    def test_binary(self, agent_response):
        """Test setting a binary response."""
        binary_data = b"Hello, world!"
        result = agent_response.binary(binary_data)
        assert result == agent_response  # Should return self for chaining
        assert agent_response.content_type == "application/octet-stream"
        assert agent_response._payload == binary_data

    def test_empty(self, agent_response):
        """Test setting an empty response."""
        result = agent_response.empty()
        assert result == agent_response  # Should return self for chaining
        assert agent_response._metadata is None

        metadata = {"key": "value"}
        result = agent_response.empty(metadata)
        assert agent_response._metadata == metadata

    def test_is_stream(self, agent_response):
        """Test is_stream property."""
        assert agent_response.is_stream is False

        agent_response._stream = iter(["chunk1", "chunk2"])
        assert agent_response.is_stream is True

    def test_stream(self, agent_response):
        """Test streaming response setup."""
        data = ["chunk1", "chunk2"]
        result = agent_response.stream(data)
        assert result == agent_response  # Should return self for chaining
        assert agent_response.content_type == "application/octet-stream"
        assert agent_response._payload is None
        assert agent_response._metadata is None
        assert agent_response._stream == data
        assert agent_response._transform is None

        def transform_fn(x):
            return f"transformed: {x}"

        result = agent_response.stream(data, transform_fn)
        assert agent_response._transform == transform_fn

    @pytest.mark.asyncio
    async def test_iteration(self, agent_response):
        """Test iteration over streaming response."""
        agent_response._stream = None
        agent_response._payload = None
        agent_response._buffer_read = True

        with pytest.raises(StopAsyncIteration):
            await agent_response.__anext__()

        agent_response._buffer_read = False
        agent_response._payload = "test payload"
        result = await agent_response.__anext__()
        assert result == b"test payload"

        agent_response._stream = iter([b"chunk1", b"chunk2"])
        agent_response._is_async = False
        result = await agent_response.__anext__()
        assert result == b"chunk1"

        result = await agent_response.__anext__()
        assert result == b"chunk2"

        with pytest.raises(StopAsyncIteration):
            await agent_response.__anext__()

        data = iter([b"chunk1", b"chunk2"])
        agent_response._stream = data
        agent_response._transform = lambda x: f"transformed: {x}"
        result = await agent_response.__anext__()
        assert result == b"transformed: b'chunk1'"
