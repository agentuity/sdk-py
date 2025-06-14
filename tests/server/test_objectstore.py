import pytest
import sys
import json
from unittest.mock import MagicMock
import httpx
from opentelemetry import trace

sys.modules["openlit"] = MagicMock()

from agentuity.server.objectstore import ObjectStore, ObjectStorePutParams  # noqa: E402
from agentuity.server.data import Data, DataResult  # noqa: E402


class TestObjectStore:
    """Test suite for the ObjectStore class."""

    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer for testing."""
        tracer = MagicMock(spec=trace.Tracer)
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span
        return tracer

    @pytest.fixture
    def object_store(self, mock_tracer):
        """Create an ObjectStore instance for testing."""
        return ObjectStore(
            base_url="https://api.example.com",
            api_key="test_api_key",
            tracer=mock_tracer,
        )

    @pytest.mark.asyncio
    async def test_get_success(self, object_store, mock_tracer, monkeypatch):
        """Test successful retrieval of an object."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.content = b'{"message": "Hello, world!"}'

        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: mock_response)

        result = await object_store.get("test-bucket", "test-key")

        assert isinstance(result, DataResult)
        assert result.exists is True
        assert isinstance(result.data, Data)
        assert result.data.content_type == "application/json"
        text = await result.data.text()
        assert text == '{"message": "Hello, world!"}'

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("bucket", "test-bucket")
        span.set_attribute.assert_any_call("key", "test-key")
        span.add_event.assert_called_once_with("hit")
        span.set_status.assert_called_once_with(trace.StatusCode.OK)

    @pytest.mark.asyncio
    async def test_get_not_found(self, object_store, mock_tracer, monkeypatch):
        """Test retrieval of a non-existent object."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404

        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: mock_response)

        result = await object_store.get("test-bucket", "test-key")

        assert isinstance(result, DataResult)
        assert result.exists is False
        assert result.data is None

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.add_event.assert_called_once_with("miss")
        span.set_status.assert_called_once_with(trace.StatusCode.OK)

    @pytest.mark.asyncio
    async def test_get_error(self, object_store, mock_tracer, monkeypatch):
        """Test error handling during object retrieval."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: mock_response)

        with pytest.raises(Exception, match="Internal Server Error"):
            await object_store.get("test-bucket", "test-key")

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_status.assert_called_once_with(
            trace.StatusCode.ERROR, "Failed to get object"
        )

    @pytest.mark.asyncio
    async def test_get_url_encoding(self, object_store, mock_tracer, monkeypatch):
        """Test URL encoding of bucket and key names."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.content = b"test content"

        mock_get = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "get", mock_get)

        await object_store.get("test bucket/with spaces", "test key/with spaces")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args

        # Check that the URL contains properly encoded bucket and key names
        # With safe='', both spaces and forward slashes should be encoded
        assert "test%20bucket%2Fwith%20spaces" in args[0]
        assert "test%20key%2Fwith%20spaces" in args[0]

    @pytest.mark.asyncio
    async def test_put_string_data(self, object_store, mock_tracer, monkeypatch):
        """Test putting string data to object store."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)

        await object_store.put("test-bucket", "test-key", "Hello, world!")

        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args

        assert "test-bucket" in args[0]
        assert "test-key" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
        assert kwargs["headers"]["Content-Type"] == "text/plain"
        content = kwargs["content"]
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        assert content == "Hello, world!"

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("bucket", "test-bucket")
        span.set_attribute.assert_any_call("key", "test-key")
        span.set_status.assert_called_once_with(trace.StatusCode.OK)

    @pytest.mark.asyncio
    async def test_put_with_params(self, object_store, mock_tracer, monkeypatch):
        """Test putting data with custom parameters."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201

        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)

        params = ObjectStorePutParams(
            content_type="application/json", content_encoding="gzip"
        )

        await object_store.put("test-bucket", "test-key", '{"test": "data"}', params)

        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args

        assert kwargs["headers"]["Content-Type"] == "application/json"
        assert kwargs["headers"]["Content-Encoding"] == "gzip"

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("contentType", "application/json")
        span.set_attribute.assert_any_call("contentEncoding", "gzip")

    @pytest.mark.asyncio
    async def test_put_with_all_params(self, object_store, mock_tracer, monkeypatch):
        """Test putting data with all custom parameters."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201

        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)

        metadata = {"author": "test-user", "version": "1.0", "category": "documents"}
        params = ObjectStorePutParams(
            content_type="application/json",
            content_encoding="gzip",
            cache_control="max-age=3600",
            content_disposition="attachment; filename=test.json",
            content_language="en-US",
            metadata=metadata,
        )

        await object_store.put("test-bucket", "test-key", '{"test": "data"}', params)

        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args

        headers = kwargs["headers"]
        assert headers["Content-Type"] == "application/json"
        assert headers["Content-Encoding"] == "gzip"
        assert headers["Cache-Control"] == "max-age=3600"
        assert headers["Content-Disposition"] == "attachment; filename=test.json"
        assert headers["Content-Language"] == "en-US"

        assert headers["x-metadata-author"] == "test-user"
        assert headers["x-metadata-version"] == "1.0"
        assert headers["x-metadata-category"] == "documents"

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("contentType", "application/json")
        span.set_attribute.assert_any_call("contentEncoding", "gzip")
        span.set_attribute.assert_any_call("cacheControl", "max-age=3600")
        span.set_attribute.assert_any_call(
            "contentDisposition", "attachment; filename=test.json"
        )
        span.set_attribute.assert_any_call("contentLanguage", "en-US")

    @pytest.mark.asyncio
    async def test_put_with_metadata_only(self, object_store, mock_tracer, monkeypatch):
        """Test putting data with only metadata parameters."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)

        metadata = {"project": "test-project", "environment": "staging"}
        params = ObjectStorePutParams(metadata=metadata)

        await object_store.put("test-bucket", "test-key", "Hello, world!", params)

        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args

        headers = kwargs["headers"]
        assert headers["x-metadata-project"] == "test-project"
        assert headers["x-metadata-environment"] == "staging"

        # Check that other headers are not set (except defaults)
        assert "Cache-Control" not in headers
        assert "Content-Disposition" not in headers
        assert "Content-Language" not in headers
        assert "Content-Encoding" not in headers

    @pytest.mark.asyncio
    async def test_put_json_data(self, object_store, mock_tracer, monkeypatch):
        """Test putting JSON data to object store."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)

        json_data = {"message": "Hello, world!", "count": 42}
        await object_store.put("test-bucket", "test-key", json_data)

        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args

        assert kwargs["headers"]["Content-Type"] == "application/json"
        content = kwargs["content"]
        if isinstance(content, bytes):
            parsed_json = json.loads(content.decode("utf-8"))
        else:
            parsed_json = json.loads(content)

        assert parsed_json == json_data

    @pytest.mark.asyncio
    async def test_put_binary_data(self, object_store, mock_tracer, monkeypatch):
        """Test putting binary data to object store."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)

        binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # PNG header bytes
        await object_store.put("test-bucket", "test-key", binary_data)

        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args

        assert kwargs["headers"]["Content-Type"] == "application/octet-stream"
        assert kwargs["content"] == binary_data

    @pytest.mark.asyncio
    async def test_put_error(self, object_store, mock_tracer, monkeypatch):
        """Test error handling during put operation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.reason_phrase = "Internal Server Error"

        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)

        with pytest.raises(Exception, match="Internal Server Error"):
            await object_store.put("test-bucket", "test-key", "Hello, world!")

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_status.assert_called_once_with(
            trace.StatusCode.ERROR, "Failed to put object"
        )

    @pytest.mark.asyncio
    async def test_delete_success(self, object_store, mock_tracer, monkeypatch):
        """Test successful deletion of an object."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        mock_delete = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "delete", mock_delete)

        result = await object_store.delete("test-bucket", "test-key")

        assert result is True

        mock_delete.assert_called_once()
        args, kwargs = mock_delete.call_args

        assert "test-bucket" in args[0]
        assert "test-key" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("bucket", "test-bucket")
        span.set_attribute.assert_any_call("key", "test-key")
        span.add_event.assert_called_once_with("deleted", {"deleted": True})
        span.set_status.assert_called_once_with(trace.StatusCode.OK)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, object_store, mock_tracer, monkeypatch):
        """Test deletion of a non-existent object."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404

        mock_delete = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "delete", mock_delete)

        result = await object_store.delete("test-bucket", "test-key")

        assert result is False

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.add_event.assert_called_once_with("not_found", {"deleted": False})
        span.set_status.assert_called_once_with(trace.StatusCode.OK)

    @pytest.mark.asyncio
    async def test_delete_error(self, object_store, mock_tracer, monkeypatch):
        """Test error handling during delete operation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_delete = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "delete", mock_delete)

        with pytest.raises(Exception, match="Internal Server Error"):
            await object_store.delete("test-bucket", "test-key")

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_status.assert_called_once_with(
            trace.StatusCode.ERROR, "Failed to delete object"
        )

    @pytest.mark.asyncio
    async def test_create_public_url_success(
        self, object_store, mock_tracer, monkeypatch
    ):
        """Test successful creation of a public URL."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "url": "https://example.com/signed-url",
        }

        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "post", mock_post)

        result = await object_store.create_public_url("test-bucket", "test-key")

        assert result == "https://example.com/signed-url"

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args

        assert "presigned" in args[0]
        assert "test-bucket" in args[0]
        assert "test-key" in args[0]
        assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
        assert kwargs["headers"]["Content-Type"] == "application/json"

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("bucket", "test-bucket")
        span.set_attribute.assert_any_call("key", "test-key")
        span.set_status.assert_called_once_with(trace.StatusCode.OK)

    @pytest.mark.asyncio
    async def test_create_public_url_with_expiry(
        self, object_store, mock_tracer, monkeypatch
    ):
        """Test creation of a public URL with expiry duration."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "url": "https://example.com/signed-url-with-expiry",
        }

        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "post", mock_post)

        expires_duration = 3600000  # 1 hour in milliseconds
        result = await object_store.create_public_url(
            "test-bucket", "test-key", expires_duration
        )

        assert result == "https://example.com/signed-url-with-expiry"

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args

        # Check that the request body contains the expires duration
        request_body = json.loads(kwargs["content"])
        assert request_body["expires"] == expires_duration

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("expiresDuration", expires_duration)

    @pytest.mark.asyncio
    async def test_create_public_url_api_error(
        self, object_store, mock_tracer, monkeypatch
    ):
        """Test API error response for public URL creation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": False,
            "message": "Object not found",
        }

        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "post", mock_post)

        with pytest.raises(Exception, match="Object not found"):
            await object_store.create_public_url("test-bucket", "test-key")

    @pytest.mark.asyncio
    async def test_create_public_url_http_error(
        self, object_store, mock_tracer, monkeypatch
    ):
        """Test HTTP error handling for public URL creation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.reason_phrase = "Internal Server Error"

        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "post", mock_post)

        with pytest.raises(Exception, match="error creating public URL"):
            await object_store.create_public_url("test-bucket", "test-key")

        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_status.assert_called_once_with(
            trace.StatusCode.ERROR, "Failed to create public URL"
        )

    @pytest.mark.asyncio
    async def test_create_public_url_json_parse_error(
        self, object_store, mock_tracer, monkeypatch
    ):
        """Test JSON parse error handling for public URL creation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.reason_phrase = "OK"

        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "post", mock_post)

        with pytest.raises(Exception, match="error creating public URL"):
            await object_store.create_public_url("test-bucket", "test-key")


class TestObjectStorePutParams:
    """Test suite for the ObjectStorePutParams class."""

    def test_default_params(self):
        """Test default parameter values."""
        params = ObjectStorePutParams()
        assert params.content_type is None
        assert params.content_encoding is None

    def test_custom_params(self):
        """Test custom parameter values."""
        params = ObjectStorePutParams(
            content_type="application/json", content_encoding="gzip"
        )
        assert params.content_type == "application/json"
        assert params.content_encoding == "gzip"

    def test_partial_params(self):
        """Test partial parameter specification."""
        params = ObjectStorePutParams(content_type="text/plain")
        assert params.content_type == "text/plain"
        assert params.content_encoding is None

    def test_all_params(self):
        """Test all parameter values."""
        metadata = {"author": "test", "version": "1.0"}
        params = ObjectStorePutParams(
            content_type="application/json",
            content_encoding="gzip",
            cache_control="max-age=3600",
            content_disposition="attachment; filename=test.json",
            content_language="en-US",
            metadata=metadata,
        )
        assert params.content_type == "application/json"
        assert params.content_encoding == "gzip"
        assert params.cache_control == "max-age=3600"
        assert params.content_disposition == "attachment; filename=test.json"
        assert params.content_language == "en-US"
        assert params.metadata == metadata

    def test_metadata_default(self):
        """Test metadata defaults to empty dict."""
        params = ObjectStorePutParams()
        assert params.metadata == {}

    def test_metadata_none(self):
        """Test metadata None converts to empty dict."""
        params = ObjectStorePutParams(metadata=None)
        assert params.metadata == {}
