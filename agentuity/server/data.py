from typing import Optional
import base64
import json


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
        return decode_payload_bytes(self.base64)


def decode_payload(payload: str) -> str:
    return base64.b64decode(payload).decode("utf-8")


def decode_payload_bytes(payload: str) -> bytes:
    return base64.b64decode(payload)


def encode_payload(data: str) -> str:
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")
