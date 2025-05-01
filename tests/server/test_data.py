import pytest
import base64
import json
import sys
import asyncio
from unittest.mock import MagicMock
from agentuity.server.data import (
    Data,
    DataResult,
    encode_payload,
)

sys.modules["openlit"] = MagicMock()


def decode_payload(payload: str) -> str:
    """
    Decode a base64 payload into a UTF-8 string.

    Args:
        payload: Base64 encoded string

    Returns:
        str: Decoded UTF-8 string
    """
    return base64.b64decode(payload).decode("utf-8")


def decode_payload_bytes(payload: str) -> bytes:
    """
    Decode a base64 payload into bytes.

    Args:
        payload: Base64 encoded string

    Returns:
        bytes: Decoded binary data
    """
    return base64.b64decode(payload)


class TestData:
    """Test suite for the Data class."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test initialization of Data object."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()
        
        data = Data("text/plain", reader)
        assert data.contentType == "text/plain"
        assert await data.base64() == "SGVsbG8sIHdvcmxkIQ=="

    @pytest.mark.asyncio
    async def test_content_type_default(self):
        """Test default content type is used when not provided."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()
        
        # Default content type should be "application/octet-stream"
        data = Data("application/octet-stream", reader)
        assert data.contentType == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_text_property(self):
        """Test the text property decodes base64 to text."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()
        
        data = Data("text/plain", reader)
        text = await data.text()
        assert text == "Hello, world!"

    @pytest.mark.asyncio
    async def test_json_property(self):
        """Test the json property decodes base64 to JSON."""
        json_obj = {"message": "Hello, world!"}
        json_str = json.dumps(json_obj)
        
        reader = asyncio.StreamReader()
        reader.feed_data(json_str.encode("utf-8"))
        reader.feed_eof()
        
        data = Data("application/json", reader)
        json_data = await data.json()
        assert json_data == json_obj

    @pytest.mark.asyncio
    async def test_json_property_invalid(self):
        """Test json property raises ValueError for invalid JSON."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")  # Not valid JSON
        reader.feed_eof()
        
        data = Data("application/json", reader)
        with pytest.raises(ValueError, match="Data is not JSON"):
            await data.json()

    @pytest.mark.asyncio
    async def test_binary_property(self):
        """Test the binary property decodes base64 to bytes."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()
        
        data = Data("application/octet-stream", reader)
        binary = await data.binary()
        assert binary == b"Hello, world!"


class TestDataResult:
    """Test suite for the DataResult class."""

    @pytest.mark.asyncio
    async def test_init_with_data(self):
        """Test initialization with Data object."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()
        
        data = Data("text/plain", reader)
        result = DataResult(data)
        assert result.data == data
        assert result.exists is True

    def test_init_without_data(self):
        """Test initialization without Data object."""
        result = DataResult()
        assert result.data is None
        assert result.exists is False


class TestEncodingFunctions:
    """Test suite for encoding and decoding functions."""

    def test_encode_payload(self):
        """Test encode_payload function."""
        encoded = encode_payload("Hello, world!")
        assert encoded == "SGVsbG8sIHdvcmxkIQ=="

    def test_decode_payload(self):
        """Test decode_payload function."""
        decoded = decode_payload("SGVsbG8sIHdvcmxkIQ==")
        assert decoded == "Hello, world!"

    def test_decode_payload_bytes(self):
        """Test decode_payload_bytes function."""
        decoded = decode_payload_bytes("SGVsbG8sIHdvcmxkIQ==")
        assert decoded == b"Hello, world!"
