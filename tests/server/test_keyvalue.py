import pytest
import sys
import json
from unittest.mock import MagicMock
import httpx
from opentelemetry import trace

sys.modules['openlit'] = MagicMock()

from agentuity.server.keyvalue import KeyValueStore  # noqa: E402
from agentuity.server.data import Data, DataResult  # noqa: E402


class TestKeyValueStore:
    """Test suite for the KeyValueStore class."""
    
    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer for testing."""
        tracer = MagicMock(spec=trace.Tracer)
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span
        return tracer
    
    @pytest.fixture
    def key_value_store(self, mock_tracer):
        """Create a KeyValueStore instance for testing."""
        return KeyValueStore(
            base_url="https://api.example.com",
            api_key="test_api_key",
            tracer=mock_tracer
        )
    
    @pytest.mark.asyncio
    async def test_get_success(self, key_value_store, mock_tracer, monkeypatch):
        """Test successful retrieval of a value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.content = b"Hello, world!"
        
        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: mock_response)
        
        result = await key_value_store.get("test_collection", "test_key")
        
        assert isinstance(result, DataResult)
        assert result.exists is True
        assert isinstance(result.data, Data)
        assert result.data.contentType == "text/plain"
        assert result.data.text == "Hello, world!"
        
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("name", "test_collection")
        span.set_attribute.assert_any_call("key", "test_key")
        span.add_event.assert_called_once_with("hit")
        span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_get_not_found(self, key_value_store, mock_tracer, monkeypatch):
        """Test retrieval of a non-existent value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        
        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: mock_response)
        
        result = await key_value_store.get("test_collection", "test_key")
        
        assert isinstance(result, DataResult)
        assert result.exists is False
        assert result.data is None
        
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.add_event.assert_called_once_with("miss")
        span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_get_error(self, key_value_store, mock_tracer, monkeypatch):
        """Test error handling during retrieval."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: mock_response)
        
        with pytest.raises(Exception, match="Failed to get key value: 500"):
            await key_value_store.get("test_collection", "test_key")
        
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_status.assert_called_once_with(trace.StatusCode.ERROR, "Failed to get key value")
    
    @pytest.mark.asyncio
    async def test_set_string_value(self, key_value_store, mock_tracer, monkeypatch):
        """Test setting a string value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        
        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)
        
        await key_value_store.set("test_collection", "test_key", "Hello, world!")
        
        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args
        
        assert args[0] == "https://api.example.com/kv/test_collection/test_key"
        assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
        assert kwargs["headers"]["Content-Type"] == "text/plain"
        content = kwargs["content"]
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        assert content == "Hello, world!"
        
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("name", "test_collection")
        span.set_attribute.assert_any_call("key", "test_key")
        span.set_attribute.assert_any_call("contentType", "text/plain")
        span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_set_json_value(self, key_value_store, mock_tracer, monkeypatch):
        """Test setting a JSON value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        
        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)
        
        json_data = {"message": "Hello, world!"}
        await key_value_store.set("test_collection", "test_key", json_data)
        
        mock_put.assert_called_once()
        args, kwargs = mock_put.call_args
        
        assert args[0] == "https://api.example.com/kv/test_collection/test_key"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        
        content = kwargs["content"]
        if isinstance(content, bytes):
            parsed_json = json.loads(content.decode("utf-8"))
        else:
            parsed_json = json.loads(content)
            
        assert parsed_json == json_data
        
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("contentType", "application/json")
    
    @pytest.mark.asyncio
    async def test_set_invalid_ttl(self, key_value_store, monkeypatch):
        """Test setting a value with invalid TTL."""
        
        original_set = key_value_store.set
        
        async def patched_set(name, key, value, params=None):
            ttl = None
            if params is not None:
                ttl = params.get("ttl", None)
                if ttl is not None and ttl < 60:
                    raise ValueError("ttl must be at least 60 seconds")
            return await original_set(name, key, value, params)
        
        monkeypatch.setattr(key_value_store, "set", patched_set)
        
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)
        
        with pytest.raises(ValueError, match="ttl must be at least 60 seconds"):
            await key_value_store.set(
                "test_collection", 
                "test_key", 
                "Hello, world!",
                {"ttl": 30}  # Less than minimum 60 seconds
            )
            
        mock_put.assert_not_called()
        
    
    @pytest.mark.asyncio
    async def test_set_error(self, key_value_store, mock_tracer, monkeypatch):
        """Test error handling during set operation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        mock_put = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "put", mock_put)
        
        with pytest.raises(Exception, match="Failed to set key value: 500"):
            await key_value_store.set("test_collection", "test_key", "Hello, world!")
        
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_status.assert_called_once_with(trace.StatusCode.ERROR, "Failed to set key value")
    
    @pytest.mark.asyncio
    async def test_delete_success(self, key_value_store, mock_tracer, monkeypatch):
        """Test successful deletion of a value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        
        mock_delete = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "delete", mock_delete)
        
        await key_value_store.delete("test_collection", "test_key")
        
        mock_delete.assert_called_once()
        args, kwargs = mock_delete.call_args
        
        assert args[0] == "https://api.example.com/kv/test_collection/test_key"
        assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
        
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_attribute.assert_any_call("name", "test_collection")
        span.set_attribute.assert_any_call("key", "test_key")
        span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_delete_error(self, key_value_store, mock_tracer, monkeypatch):
        """Test error handling during deletion."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        mock_delete = MagicMock(return_value=mock_response)
        monkeypatch.setattr(httpx, "delete", mock_delete)
        
        with pytest.raises(Exception, match="Failed to delete key value: 500"):
            await key_value_store.delete("test_collection", "test_key")
        
        span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        span.set_status.assert_called_once_with(trace.StatusCode.ERROR, "Failed to delete key value")
