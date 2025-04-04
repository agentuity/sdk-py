from typing import Optional, Union
import base64
import json
import io
import os
from typing import IO


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

    def __init__(self, data: dict):
        """
        Initialize a Data object with a dictionary containing payload information.

        Args:
            data: Dictionary containing:
                - payload: The base64 encoded data or blob reference
                - contentType: The MIME type of the data
        """
        self._data = data
        self._is_stream = data.get("payload", "").startswith("blob:")
        self._is_loaded = False

    def _get_stream_filename(self) -> Union[str, None]:
        """
        Get the filename for a stream payload.

        Returns:
            Union[str, None]: The full path to the stream file if it's a blob,
                            None otherwise

        Raises:
            ValueError: If AGENTUITY_IO_INPUT_DIR is not set or stream file doesn't exist
        """
        if not self._is_stream:
            return None
        dir = os.environ.get("AGENTUITY_IO_INPUT_DIR", None)
        if dir is None:
            raise ValueError("AGENTUITY_IO_INPUT_DIR is not set")
        id = self._data.get("payload", "")[5:]
        fn = os.path.join(dir, id)
        if not os.path.exists(fn):
            raise ValueError(f"stream {id} does not exist in {dir}")
        return fn

    def _ensure_stream_loaded(self):
        """
        Ensure that stream data is loaded into memory if it's a blob.
        Converts the stream file content to base64 encoded string.
        """
        fn = self._get_stream_filename()
        if fn is not None:
            with open(fn, "r") as f:
                self._data["payload"] = encode_payload(f.read())
            self._is_loaded = False

    @property
    def stream(self) -> IO[bytes]:
        """
        Get the data as a stream of bytes.

        Returns:
            IO[bytes]: A file-like object providing access to the data as bytes
        """
        fn = self._get_stream_filename()
        if fn is not None:
            return open(fn, "rb")
        return io.BytesIO(decode_payload_bytes(self.base64))

    @property
    def contentType(self) -> str:
        """
        Get the content type of the data.

        Returns:
            str: The MIME type of the data. If not provided, it will be inferred from
                the data. If it cannot be inferred, returns 'application/octet-stream'
        """
        return self._data.get("contentType", "application/octet-stream")

    @property
    def base64(self) -> str:
        """
        Get the base64 encoded string of the data.

        Returns:
            str: The base64 encoded payload
        """
        self._ensure_stream_loaded()
        return self._data.get("payload", "")

    @property
    def text(self) -> bytes:
        """
        Get the data as a string.

        Returns:
            bytes: The decoded text content
        """
        return decode_payload(self.base64)

    @property
    def json(self) -> dict:
        """
        Get the data as a JSON object.

        Returns:
            dict: The parsed JSON data

        Raises:
            ValueError: If the data is not valid JSON
        """
        try:
            return json.loads(self.text)
        except Exception as e:
            raise ValueError("Data is not JSON") from e

    @property
    def binary(self) -> bytes:
        """
        Get the data as binary bytes.

        Returns:
            bytes: The raw binary data
        """
        self._ensure_stream_loaded()
        return decode_payload_bytes(self.base64)


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
