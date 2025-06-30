from typing import Optional, Union, Iterator, AsyncIterator
import base64
import json
from typing import IO
from aiohttp import StreamReader
import collections.abc
import asyncio
from agentuity.server.util import deprecated
from agentuity.server.types import (
    DataInterface,
    EmailInterface,
    DiscordMessageInterface,
)


class EmptyDataReader(StreamReader):
    def __init__(self, protocol=None, limit=1):
        super().__init__(protocol, limit)

    async def read(self) -> bytes:
        return b""

    async def readany(self) -> bytes:
        return b""

    async def readexactly(self, n: int) -> bytes:
        if n > 0:
            raise ValueError("Empty stream cannot provide requested bytes")
        return b""

    async def readline(self) -> bytes:
        return b""

    async def readchunk(self) -> tuple[bytes, bool]:
        return b"", True

    def at_eof(self) -> bool:
        return True

    def exception(self) -> Optional[Exception]:
        return None

    def set_exception(self, exc: Exception) -> None:
        pass

    def unread_data(self, data: bytes) -> None:
        pass

    def feed_eof(self) -> None:
        pass

    def feed_data(self, data: bytes) -> None:
        pass

    def begin_http_chunk_receiving(self) -> None:
        pass

    def end_http_chunk_receiving(self) -> None:
        pass


class StringStreamReader(StreamReader):
    def __init__(self, data: str, protocol=None, limit=2**16):
        super().__init__(protocol, limit)
        self._data = data.encode("utf-8")
        self._pos = 0
        self._eof = False

    def read_sync(self) -> bytes:
        if self._eof:
            return b""
        data = self._data[self._pos:]
        self._pos = len(self._data)
        self._eof = True
        return data

    async def read(self) -> bytes:
        return self.read_sync()

    async def readany(self) -> bytes:
        return await self.read()

    async def readexactly(self, n: int) -> bytes:
        if n < 0:
            raise ValueError("n must be non-negative")
        if self._eof:
            if n > 0:
                raise ValueError("Not enough data to read")
            return b""
        remaining = len(self._data) - self._pos
        if n > remaining:
            raise ValueError("Not enough data to read")
        data = self._data[self._pos: self._pos + n]
        self._pos += n
        if self._pos >= len(self._data):
            self._eof = True
        return data

    async def readline(self) -> bytes:
        if self._eof:
            return b""
        data = self._data[self._pos:]
        self._pos = len(self._data)
        self._eof = True
        return data

    async def readchunk(self) -> tuple[bytes, bool]:
        if self._eof:
            return b"", True
        data = self._data[self._pos:]
        self._pos = len(self._data)
        self._eof = True
        return data, True

    def at_eof(self) -> bool:
        return self._eof

    def exception(self) -> Optional[Exception]:
        return None

    def set_exception(self, exc: Exception) -> None:
        pass

    def unread_data(self, data: bytes) -> None:
        if self._pos < len(data):
            raise ValueError("Cannot unread more data than was read")
        self._pos -= len(data)
        self._eof = False

    def feed_eof(self) -> None:
        self._eof = True

    def feed_data(self, data: bytes) -> None:
        raise NotImplementedError(
            "StringStreamReader does not support feeding data")

    def begin_http_chunk_receiving(self) -> None:
        pass

    def end_http_chunk_receiving(self) -> None:
        pass


class BytesStreamReader(StreamReader):
    def __init__(self, data: bytes, protocol=None, limit=2**16):
        super().__init__(protocol, limit)
        self._data = data
        self._pos = 0
        self._eof = False

    def read_sync(self) -> bytes:
        if self._eof:
            return b""
        data = self._data[self._pos:]
        self._pos = len(self._data)
        self._eof = True
        return data

    async def read(self) -> bytes:
        return self.read_sync()

    async def readany(self) -> bytes:
        return await self.read()

    async def readexactly(self, n: int) -> bytes:
        if n < 0:
            raise ValueError("n must be non-negative")
        if self._eof:
            if n > 0:
                raise ValueError("Not enough data to read")
            return b""
        remaining = len(self._data) - self._pos
        if n > remaining:
            raise ValueError("Not enough data to read")
        data = self._data[self._pos: self._pos + n]
        self._pos += n
        if self._pos >= len(self._data):
            self._eof = True
        return data

    async def readline(self) -> bytes:
        if self._eof:
            return b""
        data = self._data[self._pos:]
        self._pos = len(self._data)
        self._eof = True
        return data

    async def readchunk(self) -> tuple[bytes, bool]:
        if self._eof:
            return b"", True
        data = self._data[self._pos:]
        self._pos = len(self._data)
        self._eof = True
        return data, True

    def at_eof(self) -> bool:
        return self._eof

    def exception(self) -> Optional[Exception]:
        return None

    def set_exception(self, exc: Exception) -> None:
        pass

    def unread_data(self, data: bytes) -> None:
        if self._pos < len(data):
            raise ValueError("Cannot unread more data than was read")
        self._pos -= len(data)
        self._eof = False

    def feed_eof(self) -> None:
        self._eof = True

    def feed_data(self, data: bytes) -> None:
        raise NotImplementedError(
            "BytesStreamReader does not support feeding data")

    def begin_http_chunk_receiving(self) -> None:
        pass

    def end_http_chunk_receiving(self) -> None:
        pass


class DataResult:
    """
    A container class for the result of a data operation, providing access to the data
    and information about whether the data exists.
    """

    def __init__(self, data: Optional["Data"] = None):
        """
        Initialize a DataResult with optional data.

        Args:
            data: Optional Data object containing the result data
        """
        if data is None:
            self._exists = False
            self._data = Data("application/octet-stream", EmptyDataReader())
        else:
            self._exists = True
            self._data = data

    @property
    def data(self) -> Optional["Data"]:
        """
        Get the data from the result of the operation.

        Returns:
            Optional[Data]: The data object containing the result content, or None if exists is False
        """
        return None if not self._exists else self._data

    @property
    def exists(self) -> bool:
        """
        Check if the data was found.

        Returns:
            bool: True if the data exists, False otherwise
        """
        return self._exists

    def __str__(self) -> str:
        """
        Get a string representation of the data result.

        Returns:
            str: A formatted string containing the content type and payload
        """
        return f"DataResult(data={self._data})"


class Data(DataInterface):
    """
    A container class for working with agent data payloads. This class provides methods
    to handle different types of data (text, JSON, binary) and supports streaming
    functionality for large payloads.
    """

    def __init__(self, contentType: str, stream: StreamReader):
        """
        Initialize a Data object with a dictionary containing payload information.

        Args:
            data: Dictionary containing:
        """
        self._contentType = contentType
        self._stream = stream
        self._loaded = False
        self._data = None

    async def _ensure_stream_loaded(self):
        if not self._loaded:
            self._loaded = True
            self._data = await self._stream.read()
        return self._data

    async def stream(self) -> IO[bytes]:
        """
        Get the data as a stream of bytes.

        Returns:
            IO[bytes]: A file-like object providing access to the data as bytes
        """
        if self._loaded:
            return BytesStreamReader(self._data)
        return self._stream

    @deprecated("Use content_type instead")
    @property
    def contentType(self) -> str:
        """
        Get the content type of the data.

        Returns:
            str: The MIME type of the data. If not provided, it will be inferred from
                the data. If it cannot be inferred, returns 'application/octet-stream'
        """
        return self.content_type

    @property
    def content_type(self) -> str:
        """
        Get the content type of the data.

        Returns:
            str: The MIME type of the data. If not provided, it will be inferred from
                the data. If it cannot be inferred, returns 'application/octet-stream'
        """
        return self._contentType

    async def base64(self) -> str:
        """
        Get the base64 encoded string of the data.

        Returns:
            str: The base64 encoded payload
        """
        data = await self._ensure_stream_loaded()
        return encode_payload(data)

    async def text(self) -> str:
        """
        Get the data as a string.

        Returns:
            bytes: The decoded text content
        """
        data = await self._ensure_stream_loaded()
        return data.decode("utf-8")

    async def json(self) -> dict:
        """
        Get the data as a JSON object.

        Returns:
            dict: The parsed JSON data

        Raises:
            ValueError: If the data is not valid JSON
        """
        try:
            return json.loads(await self.text())
        except Exception as e:
            raise ValueError(f"Data is not JSON: {e}") from e

    async def binary(self) -> bytes:
        """
        Get the data as binary bytes.

        Returns:
            bytes: The raw binary data
        """
        data = await self._ensure_stream_loaded()
        return data

    def _ensure_stream_loaded_sync(self):
        if not self._loaded:
            # Try to read synchronously
            if hasattr(self._stream, "read_sync"):
                data = self._stream.read_sync()
                self._data = data
                self._loaded = True
            elif hasattr(self._stream, "read"):
                # Avoid instantiating a coroutine – check the *function* first
                if asyncio.iscoroutinefunction(self._stream.read):
                    raise RuntimeError(
                        "This Data instance requires async access")
                data = self._stream.read()  # guaranteed to be bytes now
                self._data = data
                self._loaded = True
            else:
                raise RuntimeError("This Data instance requires async access")
        return self._data

    async def email(self) -> "EmailInterface":
        if self._contentType != "message/rfc822":
            raise ValueError("The content type is not a valid email")

        from agentuity.io.email import Email

        text = await self.text()
        return Email(text)

    async def discord(self) -> "DiscordMessageInterface":
        from agentuity.io.discord import DiscordMessage

        text = await self.text()
        return DiscordMessage(text)


def encode_payload(data: Union[str, bytes]) -> str:
    """
    Encode a string or bytes into base64.

    Args:
        data: UTF-8 string or bytes to encode

    Returns:
        str: Base64 encoded string
    """
    if isinstance(data, bytes):
        return base64.b64encode(data).decode("utf-8")
    else:
        return base64.b64encode(data.encode("utf-8")).decode("utf-8")


class IteratorStreamReader(StreamReader):
    def __init__(self, iterator: Iterator[bytes], protocol=None, limit=2**16):
        super().__init__(protocol, limit)
        self._iterator = iterator
        self._buffer = b""
        self._eof = False

    async def read(self) -> bytes:
        if self._eof:
            return b""
        try:
            chunks = []
            while True:
                try:
                    chunk = next(self._iterator)
                    chunks.append(chunk)
                except StopIteration:
                    break
            self._eof = True
            return b"".join(chunks)
        except Exception as e:
            self.set_exception(e)
            raise

    async def readany(self) -> bytes:
        return await self.read()

    async def readexactly(self, n: int) -> bytes:
        if n < 0:
            raise ValueError("n must be non-negative")
        if self._eof:
            if n > 0:
                raise ValueError("Not enough data to read")
            return b""

        while len(self._buffer) < n:
            try:
                chunk = next(self._iterator)
                self._buffer += chunk
            except StopIteration:
                self._eof = True
                if len(self._buffer) < n:
                    raise ValueError("Not enough data to read") from None
                break

        result = self._buffer[:n]
        self._buffer = self._buffer[n:]
        return result

    async def readline(self) -> bytes:
        return await self.read()

    async def readchunk(self) -> tuple[bytes, bool]:
        if self._eof:
            return b"", True
        try:
            chunk = next(self._iterator)
            return chunk, False
        except StopIteration:
            self._eof = True
            return b"", True

    def at_eof(self) -> bool:
        return self._eof

    def exception(self) -> Optional[Exception]:
        return None

    def set_exception(self, exc: Exception) -> None:
        pass

    def unread_data(self, data: bytes) -> None:
        self._buffer = data + self._buffer
        self._eof = False

    def feed_eof(self) -> None:
        self._eof = True

    def feed_data(self, data: bytes) -> None:
        raise NotImplementedError(
            "IteratorStreamReader does not support feeding data")

    def begin_http_chunk_receiving(self) -> None:
        pass

    def end_http_chunk_receiving(self) -> None:
        pass


class EmptyAsyncIterator:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class AsyncChain:
    def __init__(self, first, rest):
        self._first = first
        self._rest = rest
        self._first_yielded = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._first_yielded:
            self._first_yielded = True
            return self._first
        return await anext(self._rest)


async def validate_async_iterator(
    iterator: AsyncIterator[bytes],
) -> AsyncIterator[bytes]:
    """
    Validate that an async iterator yields bytes and reconstruct it with the first item.

    Args:
        iterator: The async iterator to validate

    Returns:
        AsyncIterator[bytes]: A validated async iterator that yields bytes

    Raises:
        ValueError: If the iterator yields non-bytes data
    """
    try:
        first = await anext(iterator)
    except StopAsyncIteration:
        return EmptyAsyncIterator()

    if not isinstance(first, (bytes, bytearray)):
        raise ValueError("Async iterator must yield bytes")

    return AsyncChain(first, iterator)


class AsyncIteratorStreamReader(StreamReader):
    def __init__(self, iterator: AsyncIterator[bytes], protocol=None, limit=2**16):
        super().__init__(protocol, limit)
        self._iterator = iterator
        self._buffer = b""
        self._eof = False

    async def read(self) -> bytes:
        if self._eof:
            return b""
        try:
            chunks = []
            async for chunk in self._iterator:
                chunks.append(chunk)
            self._eof = True
            return b"".join(chunks)
        except Exception as e:
            self.set_exception(e)
            raise

    async def readany(self) -> bytes:
        return await self.read()

    async def readexactly(self, n: int) -> bytes:
        if n < 0:
            raise ValueError("n must be non-negative")
        if self._eof:
            if n > 0:
                raise ValueError("Not enough data to read")
            return b""

        while len(self._buffer) < n:
            try:
                chunk = await anext(self._iterator)
                self._buffer += chunk
            except StopAsyncIteration:
                self._eof = True
                if len(self._buffer) < n:
                    raise ValueError("Not enough data to read") from None
                break

        result = self._buffer[:n]
        self._buffer = self._buffer[n:]
        return result

    async def readline(self) -> bytes:
        return await self.read()

    async def readchunk(self) -> tuple[bytes, bool]:
        if self._eof:
            return b"", True
        try:
            chunk = await anext(self._iterator)
            return chunk, False
        except StopAsyncIteration:
            self._eof = True
            return b"", True

    def at_eof(self) -> bool:
        return self._eof

    def exception(self) -> Optional[Exception]:
        return None

    def set_exception(self, exc: Exception) -> None:
        pass

    def unread_data(self, data: bytes) -> None:
        self._buffer = data + self._buffer
        self._eof = False

    def feed_eof(self) -> None:
        self._eof = True

    def feed_data(self, data: bytes) -> None:
        raise NotImplementedError(
            "AsyncIteratorStreamReader does not support feeding data"
        )

    def begin_http_chunk_receiving(self) -> None:
        pass

    def end_http_chunk_receiving(self) -> None:
        pass


class ValidatedAsyncIterator:
    def __init__(self, iterator: AsyncIterator[bytes]):
        self._iterator = iterator
        self._validated = False
        self._first = None
        self._first_yielded = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._validated:
            try:
                self._first = await anext(self._iterator)
                if not isinstance(self._first, (bytes, bytearray)):
                    raise ValueError("Async iterator must yield bytes")
                self._validated = True
            except StopAsyncIteration:
                self._validated = True
                raise

        if not self._first_yielded:
            self._first_yielded = True
            return self._first

        return await anext(self._iterator)


DataLike = Union[
    str,
    int,
    float,
    bool,
    list,
    dict,
    bytes,
    "Data",
    StreamReader,
    Iterator[bytes],
    AsyncIterator[bytes],
]


def dataLikeToData(value: DataLike, content_type: str = None) -> Data:
    """
    Convert a value to a Data object.

    Args:
        value: The value to convert. Can be:
            - Data object
            - bytes
            - str, int, float, bool
            - list or dict (will be converted to JSON)
            - StreamReader
            - Iterator[bytes]
            - AsyncIterator[bytes]
        content_type: The desired content type for the payload to override the inferred type

    Returns:
        Data: The Data object containing

    Raises:
        ValueError: If the value type is not supported
    """
    if isinstance(value, Data):
        return value
    elif isinstance(value, bytes):
        content_type = content_type or "application/octet-stream"
        return Data(content_type, BytesStreamReader(value))
    elif isinstance(value, (str, int, float, bool)):
        content_type = content_type or "text/plain"
        payload = str(value)
        return Data(content_type, StringStreamReader(payload))
    elif isinstance(value, (list, dict)):
        content_type = content_type or "application/json"
        payload = json.dumps(value)
        return Data(content_type, StringStreamReader(payload))
    elif isinstance(value, (StreamReader, asyncio.StreamReader)):
        content_type = content_type or "application/octet-stream"
        return Data(content_type, value)
    elif isinstance(value, collections.abc.Iterator):
        import itertools

        content_type = content_type or "application/octet-stream"
        # ensure this iterator yields bytes
        try:
            first = next(value)
        except StopIteration:
            validated_iter = iter(())
        else:
            if not isinstance(first, (bytes, bytearray)):
                raise ValueError("Iterator must yield bytes")
            validated_iter = itertools.chain([first], value)
        return Data(content_type, IteratorStreamReader(validated_iter))
    elif isinstance(value, collections.abc.AsyncIterator):
        content_type = content_type or "application/octet-stream"
        return Data(
            content_type, AsyncIteratorStreamReader(
                ValidatedAsyncIterator(value))
        )
    else:
        raise ValueError(f"Unsupported value type: {type(value)}")
