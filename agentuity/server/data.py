from typing import Optional, Union
import base64
import json
import io
import os
from typing import IO


class DataResult:
    def __init__(self, data: Optional["Data"] = None):
        self._data = data

    @property
    def data(self) -> "Data":
        """
        the data from the result of the operation
        """
        return self._data

    @property
    def exists(self) -> bool:
        """
        true if the data was found
        """
        return self._data is not None

    def __str__(self) -> str:
        return f"DataResult(contentType={self._data.contentType}, payload={self._data.base64})"


class Data:
    """
    Data is a container class for working with the payload of an agent data
    """

    def __init__(self, data: dict):
        self._data = data
        self._is_stream = data.get("payload", "").startswith("blob:")
        self._is_loaded = False

    def _get_stream_filename(self) -> Union[str, None]:
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
        fn = self._get_stream_filename()
        if fn is not None:
            with open(fn, "r") as f:
                self._data["payload"] = encode_payload(f.read())
            self._is_loaded = False

    @property
    def stream(self) -> IO[bytes]:
        """
        an IO[bytes] object as a stream of the data
        """
        fn = self._get_stream_filename()
        if fn is not None:
            return open(fn, "rb")
        return io.BytesIO(decode_payload_bytes(self.base64))

    @property
    def contentType(self) -> str:
        """
        the content type of the data such as 'text/plain', 'application/json', 'image/png', etc. if no content type is provided, it will be inferred from the data.
        if it cannot be inferred, it will be 'application/octet-stream'.
        """
        return self._data.get("contentType", "application/octet-stream")

    @property
    def base64(self) -> str:
        """
        base64 encoded string of the data
        """
        self._ensure_stream_loaded()
        return self._data.get("payload", "")

    @property
    def text(self) -> bytes:
        """
        the data represented as a string
        """
        return decode_payload(self.base64)

    @property
    def json(self) -> dict:
        """
        the JSON data. If the data is not JSON, this will throw a ValueError.
        """
        try:
            return json.loads(self.text)
        except Exception as e:
            raise ValueError("Data is not JSON") from e

    @property
    def binary(self) -> bytes:
        """
        the binary data represented as a bytes object
        """
        self._ensure_stream_loaded()
        return decode_payload_bytes(self.base64)


def decode_payload(payload: str) -> str:
    return base64.b64decode(payload).decode("utf-8")


def decode_payload_bytes(payload: str) -> bytes:
    return base64.b64decode(payload)


def encode_payload(data: str) -> str:
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")


def value_to_payload(
    content_type: str, value: Union[str, int, float, bool, list, dict, bytes, "Data"]
) -> dict:
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
