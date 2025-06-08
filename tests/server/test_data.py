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
    dataLikeToData,
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
        assert data.content_type == "text/plain"
        assert await data.base64() == "SGVsbG8sIHdvcmxkIQ=="

    @pytest.mark.asyncio
    async def test_content_type_default(self):
        """Test default content type is used when not provided."""
        reader = asyncio.StreamReader()
        reader.feed_data(b"Hello, world!")
        reader.feed_eof()

        # Default content type should be "application/octet-stream"
        data = Data("application/octet-stream", reader)
        assert data.content_type == "application/octet-stream"

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


class TestDataLikeToData:
    """Test suite for the dataLikeToData function."""

    @pytest.mark.asyncio
    async def test_bytes_iterator(self):
        """Test converting a bytes iterator to Data."""
        chunks = [b"Hello", b", ", b"world", b"!"]
        iterator = iter(chunks)

        data = dataLikeToData(iterator)
        assert data.content_type == "application/octet-stream"
        assert await data.binary() == b"Hello, world!"

    @pytest.mark.asyncio
    async def test_bytes_iterator_with_content_type(self):
        """Test converting a bytes iterator to Data with custom content type."""
        chunks = [b"Hello", b", ", b"world", b"!"]
        iterator = iter(chunks)

        data = dataLikeToData(iterator, content_type="text/plain")
        assert data.content_type == "text/plain"
        assert await data.binary() == b"Hello, world!"

    @pytest.mark.asyncio
    async def test_empty_iterator(self):
        """Test converting an empty iterator to Data."""
        iterator = iter([])

        data = dataLikeToData(iterator)
        assert data.content_type == "application/octet-stream"
        assert await data.binary() == b""

    @pytest.mark.asyncio
    async def test_large_iterator(self):
        """Test converting a large iterator to Data."""
        chunks = [b"x" * 1024 for _ in range(10)]  # 10KB of data
        iterator = iter(chunks)

        data = dataLikeToData(iterator)
        assert data.content_type == "application/octet-stream"
        result = await data.binary()
        assert len(result) == 10240  # 10KB
        assert result == b"x" * 10240  # Check that all bytes are 'x'

    @pytest.mark.asyncio
    async def test_mixed_chunk_sizes(self):
        """Test converting an iterator with mixed chunk sizes to Data."""
        chunks = [b"Hello", b"", b", ", b"world", b"!", b""]
        iterator = iter(chunks)

        data = dataLikeToData(iterator)
        assert data.content_type == "application/octet-stream"
        assert await data.binary() == b"Hello, world!"

    @pytest.mark.asyncio
    async def test_str(self):
        data = dataLikeToData("hello world")
        assert data.content_type == "text/plain"
        assert await data.text() == "hello world"

    @pytest.mark.asyncio
    async def test_int(self):
        data = dataLikeToData(42)
        assert data.content_type == "text/plain"
        assert await data.text() == "42"

    @pytest.mark.asyncio
    async def test_float(self):
        data = dataLikeToData(3.14)
        assert data.content_type == "text/plain"
        assert await data.text() == "3.14"

    @pytest.mark.asyncio
    async def test_bool(self):
        data = dataLikeToData(True)
        assert data.content_type == "text/plain"
        assert await data.text() == "True"

    @pytest.mark.asyncio
    async def test_list(self):
        value = [1, 2, 3]
        data = dataLikeToData(value)
        assert data.content_type == "application/json"
        assert await data.json() == value

    @pytest.mark.asyncio
    async def test_dict(self):
        value = {"a": 1, "b": 2}
        data = dataLikeToData(value)
        assert data.content_type == "application/json"
        assert await data.json() == value

    @pytest.mark.asyncio
    async def test_bytes(self):
        value = b"bytes data"
        data = dataLikeToData(value)
        assert data.content_type == "application/octet-stream"
        assert await data.binary() == value

    @pytest.mark.asyncio
    async def test_data(self):
        # Passing a Data object should return the same object
        orig = dataLikeToData("hello")
        data = dataLikeToData(orig)
        assert data is orig
        assert await data.text() == "hello"

    @pytest.mark.asyncio
    async def test_streamreader(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b"streamreader data")
        reader.feed_eof()
        data = dataLikeToData(reader)
        assert data.content_type == "application/octet-stream"
        assert await data.binary() == b"streamreader data"

    @pytest.mark.asyncio
    async def test_async_iterator(self):
        """Test converting an async iterator to Data."""

        async def gen():
            yield b"Hello"
            yield b", "
            yield b"world"
            yield b"!"

        data = dataLikeToData(gen())
        assert data.content_type == "application/octet-stream"
        assert await data.binary() == b"Hello, world!"

    @pytest.mark.asyncio
    async def test_async_iterator_with_content_type(self):
        """Test converting an async iterator to Data with custom content type."""

        async def gen():
            yield b"Hello"
            yield b", "
            yield b"world"
            yield b"!"

        data = dataLikeToData(gen(), content_type="text/plain")
        assert data.content_type == "text/plain"
        assert await data.binary() == b"Hello, world!"

    @pytest.mark.asyncio
    async def test_empty_async_iterator(self):
        """Test converting an empty async iterator to Data."""

        async def gen():
            if False:
                yield b""

        data = dataLikeToData(gen())
        assert data.content_type == "application/octet-stream"
        assert await data.binary() == b""

    @pytest.mark.asyncio
    async def test_large_async_iterator(self):
        """Test converting a large async iterator to Data."""

        async def gen():
            for _ in range(10):
                yield b"x" * 1024  # 10KB of data

        data = dataLikeToData(gen())
        assert data.content_type == "application/octet-stream"
        result = await data.binary()
        assert len(result) == 10240  # 10KB
        assert result == b"x" * 10240

    @pytest.mark.asyncio
    async def test_mixed_chunk_sizes_async_iterator(self):
        """Test converting an async iterator with mixed chunk sizes to Data."""

        async def gen():
            yield b"Hello"
            yield b""
            yield b", "
            yield b"world"
            yield b"!"
            yield b""

        data = dataLikeToData(gen())
        assert data.content_type == "application/octet-stream"
        assert await data.binary() == b"Hello, world!"
