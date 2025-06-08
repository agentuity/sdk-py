import pytest
import sys
import asyncio
from unittest.mock import MagicMock

sys.modules["openlit"] = MagicMock()

from agentuity.server.request import AgentRequest  # noqa: E402
from agentuity.server.data import Data  # noqa: E402


class TestAgentRequest:
    """Test suite for the AgentRequest class."""

    def test_init(self):
        """Test initialization of AgentRequest."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        request = AgentRequest("manual", {"key": "value"}, "text/plain", reader)

        assert isinstance(request, AgentRequest)
        assert isinstance(request.data, Data)
        assert request.data.content_type == "text/plain"
        assert request.trigger == "manual"

    @pytest.mark.asyncio
    async def test_data_property(self):
        """Test the data property returns the Data object."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        request = AgentRequest("manual", {"key": "value"}, "text/plain", reader)
        assert isinstance(request.data, Data)
        assert await request.data.text() == "Hello, world!"

    def test_data_property_sync(self):
        """Test the data property returns the Data object (sync check)."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        request = AgentRequest("manual", {"key": "value"}, "text/plain", reader)
        assert isinstance(request.data, Data)

    def test_trigger_property(self):
        """Test the trigger property returns the trigger value."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        request = AgentRequest("manual", {"key": "value"}, "text/plain", reader)
        assert request.trigger == "manual"

    def test_metadata_property(self):
        """Test the metadata property returns the metadata dict."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        request = AgentRequest("manual", {"key": "value"}, "text/plain", reader)
        assert request.metadata == {"key": "value"}

    def test_metadata_default(self):
        """Test metadata property returns empty dict if not present."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        request = AgentRequest("manual", {}, "text/plain", reader)
        assert request.metadata == {}

    def test_get_method(self):
        """Test get method retrieves value from metadata."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        request = AgentRequest("manual", {"key": "value"}, "text/plain", reader)
        assert request.get("key") == "value"
        assert request.get("non_existent") is None
        assert request.get("non_existent", "default") == "default"
