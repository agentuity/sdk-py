from typing import Optional, Union
import base64
import json
from typing import IO
from aiohttp import StreamReader


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
        self._data = data

    @property
    def data(self) -> "Data":
        """
        Get the data from the result of the operation.

        Returns:
            Data: The data object containing the result content
        """
        return self._data

    @property
    def exists(self) -> bool:
        """
        Check if the data was found.

        Returns:
            bool: True if the data exists, False otherwise
        """
        return self._data is not None

    def __str__(self) -> str:
        """
        Get a string representation of the data result.

        Returns:
            str: A formatted string containing the content type and payload
        """
        return f"DataResult(contentType={self._data.contentType}, payload={self._data.base64})"


class Data:
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
            raise ValueError("Stream already loaded")
        return self._stream

    @property
    def contentType(self) -> str:
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

    async def text(self) -> bytes:
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


def value_to_payload(
    content_type: str, value: Union[str, int, float, bool, list, dict, bytes, "Data"]
) -> dict:
    """
    Convert a value to a payload dictionary with appropriate content type.

    Args:
        content_type: The desired content type for the payload
        value: The value to convert. Can be:
            - Data object
            - bytes
            - str, int, float, bool
            - list or dict (will be converted to JSON)

    Returns:
        dict: Dictionary containing:
            - contentType: The content type of the payload
            - payload: The encoded payload data

    Raises:
        ValueError: If the value type is not supported
    """
    if isinstance(value, Data):
        content_type = content_type or value.contentType
        payload = base64.b64decode(value.base64)
        return {"contentType": content_type, "payload": payload}
    elif isinstance(value, bytes):
        content_type = content_type or "application/octet-stream"
        payload = value
        return {"contentType": content_type, "payload": payload}
    elif isinstance(value, (str, int, float, bool)):
        content_type = content_type or "text/plain"
        payload = str(value)
        return {"contentType": content_type, "payload": payload}
    elif isinstance(value, (list, dict)):
        content_type = content_type or "application/json"
        payload = json.dumps(value)
        return {"contentType": content_type, "payload": payload}
    else:
        raise ValueError(f"Unsupported value type: {type(value)}")
