import pytest
import sys
import json
from unittest.mock import patch, MagicMock
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
    async def test_get_success(self, key_value_store, mock_tracer):
        """Test successful retrieval of a value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.content = b"Hello, world!"
        
        with patch("httpx.get", return_value=mock_response):
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
    async def test_get_not_found(self, key_value_store, mock_tracer):
        """Test retrieval of a non-existent value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        
        with patch("httpx.get", return_value=mock_response):
            result = await key_value_store.get("test_collection", "test_key")
            
            assert isinstance(result, DataResult)
            assert result.exists is False
            assert result.data is None
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.add_event.assert_called_once_with("miss")
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_get_error(self, key_value_store, mock_tracer):
        """Test error handling during retrieval."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        
        with patch("httpx.get", return_value=mock_response), \
             pytest.raises(Exception, match="Failed to get key value: 500"):
            await key_value_store.get("test_collection", "test_key")
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_status.assert_called_once_with(
                trace.StatusCode.ERROR, 
                "Failed to get key value"
            )
    
    @pytest.mark.asyncio
    async def test_set_string_value(self, key_value_store, mock_tracer):
        """Test setting a string value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        
        with patch("httpx.put", return_value=mock_response):
            await key_value_store.set("test_collection", "test_key", "Hello, world!")
            
            httpx.put.assert_called_once()
            args, kwargs = httpx.put.call_args
            
            assert args[0] == "https://api.example.com/kv/test_collection/test_key"
            assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
            assert kwargs["headers"]["Content-Type"] == "text/plain"
            assert kwargs["content"] == b"Hello, world!"
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_attribute.assert_any_call("name", "test_collection")
            span.set_attribute.assert_any_call("key", "test_key")
            span.set_attribute.assert_any_call("contentType", "text/plain")
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_set_json_value(self, key_value_store, mock_tracer):
        """Test setting a JSON value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        
        json_data = {"message": "Hello, world!"}
        
        with patch("httpx.put", return_value=mock_response):
            await key_value_store.set("test_collection", "test_key", json_data)
            
            httpx.put.assert_called_once()
            args, kwargs = httpx.put.call_args
            
            assert args[0] == "https://api.example.com/kv/test_collection/test_key"
            assert kwargs["headers"]["Content-Type"] == "application/json"
            assert json.loads(kwargs["content"].decode("utf-8")) == json_data
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_attribute.assert_any_call("contentType", "application/json")
    
    @pytest.mark.asyncio
    async def test_set_with_ttl(self, key_value_store, mock_tracer):
        """Test setting a value with TTL."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        
        with patch("httpx.put", return_value=mock_response):
            await key_value_store.set(
                "test_collection", 
                "test_key", 
                "Hello, world!",
                {"ttl": 3600}  # 1 hour TTL
            )
            
            httpx.put.assert_called_once()
            args, kwargs = httpx.put.call_args
            
            assert "/3600" in args[0]
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_attribute.assert_any_call("ttl", "/3600")
    
    @pytest.mark.asyncio
    async def test_set_invalid_ttl(self, key_value_store):
        """Test setting a value with invalid TTL."""
        with pytest.raises(ValueError, match="ttl must be at least 60 seconds"):
            await key_value_store.set(
                "test_collection", 
                "test_key", 
                "Hello, world!",
                {"ttl": 30}  # Less than minimum 60 seconds
            )
    
    @pytest.mark.asyncio
    async def test_set_error(self, key_value_store, mock_tracer):
        """Test error handling during set operation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        
        with patch("httpx.put", return_value=mock_response), \
             pytest.raises(Exception, match="Failed to set key value: 500"):
            await key_value_store.set("test_collection", "test_key", "Hello, world!")
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_status.assert_called_once_with(
                trace.StatusCode.ERROR, 
                "Failed to set key value"
            )
    
    @pytest.mark.asyncio
    async def test_delete_success(self, key_value_store, mock_tracer):
        """Test successful deletion of a value."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        
        with patch("httpx.delete", return_value=mock_response):
            await key_value_store.delete("test_collection", "test_key")
            
            httpx.delete.assert_called_once()
            args, kwargs = httpx.delete.call_args
            
            assert args[0] == "https://api.example.com/kv/test_collection/test_key"
            assert kwargs["headers"]["Authorization"] == "Bearer test_api_key"
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_attribute.assert_any_call("name", "test_collection")
            span.set_attribute.assert_any_call("key", "test_key")
            span.set_status.assert_called_once_with(trace.StatusCode.OK)
    
    @pytest.mark.asyncio
    async def test_delete_error(self, key_value_store, mock_tracer):
        """Test error handling during deletion."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        
        with patch("httpx.delete", return_value=mock_response), \
             pytest.raises(Exception, match="Failed to delete key value: 500"):
            await key_value_store.delete("test_collection", "test_key")
            
            span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
            span.set_status.assert_called_once_with(
                trace.StatusCode.ERROR, 
                "Failed to delete key value"
            )
