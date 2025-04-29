import pytest
import base64
import json
import sys
from unittest.mock import MagicMock
from agentuity.server.data import (
    Data,
    DataResult,
    encode_payload,
    decode_payload,
    decode_payload_bytes,
)

sys.modules["openlit"] = MagicMock()


class TestData:
    """Test suite for the Data class."""

    def test_init(self):
        """Test initialization of Data object."""
        data_dict = {
            "contentType": "text/plain",
            "payload": "SGVsbG8sIHdvcmxkIQ==",  # "Hello, world!" in base64
        }
        data = Data(data_dict)
        assert data.contentType == "text/plain"
        assert data.base64 == "SGVsbG8sIHdvcmxkIQ=="

    def test_content_type_default(self):
        """Test default content type is used when not provided."""
        data_dict = {
            "payload": "SGVsbG8sIHdvcmxkIQ==",
        }
        data = Data(data_dict)
        assert data.contentType == "application/octet-stream"

    def test_text_property(self):
        """Test the text property decodes base64 to text."""
        data_dict = {
            "contentType": "text/plain",
            "payload": "SGVsbG8sIHdvcmxkIQ==",  # "Hello, world!" in base64
        }
        data = Data(data_dict)
        assert data.text == "Hello, world!"

    def test_json_property(self):
        """Test the json property decodes base64 to JSON."""
        json_obj = {"message": "Hello, world!"}
        json_str = json.dumps(json_obj)
        data_dict = {
            "contentType": "application/json",
            "payload": base64.b64encode(json_str.encode("utf-8")).decode("utf-8"),
        }
        data = Data(data_dict)
        assert data.json == json_obj

    def test_json_property_invalid(self):
        """Test json property raises ValueError for invalid JSON."""
        data_dict = {
            "contentType": "application/json",
            "payload": "SGVsbG8sIHdvcmxkIQ==",  # "Hello, world!" in base64, not valid JSON
        }
        data = Data(data_dict)
        with pytest.raises(ValueError, match="Data is not JSON"):
            data.json

    def test_binary_property(self):
        """Test the binary property decodes base64 to bytes."""
        data_dict = {
            "contentType": "application/octet-stream",
            "payload": "SGVsbG8sIHdvcmxkIQ==",  # "Hello, world!" in base64
        }
        data = Data(data_dict)
        assert data.binary == b"Hello, world!"


class TestDataResult:
    """Test suite for the DataResult class."""

    def test_init_with_data(self):
        """Test initialization with Data object."""
        data_dict = {
            "contentType": "text/plain",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
        }
        data = Data(data_dict)
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
