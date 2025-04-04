import pytest
import sys
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp.web import Request, Response, Application
from opentelemetry import trace

sys.modules['openlit'] = MagicMock()

from agentuity.server import (  # noqa: E402
    handle_agent_request,
    handle_run_request,
    handle_health_check,
    handle_index,
    inject_trace_context
)
from agentuity.server.response import AgentResponse  # noqa: E402


class TestRequestHandlers:
    """Test suite for server request handlers."""
    
    @pytest.fixture
    def mock_app(self):
        """Create a mock application with agents_by_id."""
        app = MagicMock(spec=Application)
        app.__getitem__.return_value = {
            "test_agent": {
                "id": "test_agent",
                "name": "Test Agent",
                "run": AsyncMock(return_value="Test response"),
            }
        }
        return app
    
    @pytest.fixture
    def mock_request(self, mock_app):
        """Create a mock request object."""
        request = MagicMock(spec=Request)
        request.app = mock_app
        request.match_info = {"agent_id": "test_agent"}
        request.headers = {"Content-Type": "application/json"}
        request.json = AsyncMock(return_value={"message": "Hello, world!"})
        request.host = "localhost"
        request.path = "/test_agent"
        request.url = "http://localhost/test_agent"
        return request
    
    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer."""
        tracer = MagicMock(spec=trace.Tracer)
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span
        return tracer
    
    @pytest.mark.asyncio
    async def test_handle_health_check(self):
        """Test health check endpoint."""
        request = MagicMock()
        response = await handle_health_check(request)
        assert response.status == 200
        response_text = response.text
        response_json = json.loads(response_text)
        assert response_json == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_handle_index(self, mock_request):
        """Test index endpoint."""
        response = await handle_index(mock_request)
        assert response.status == 200
        assert response.content_type == "text/plain"
        assert "The following Agent routes are available:" in response.text
        assert "POST /run/test_agent" in response.text
    
    @pytest.mark.asyncio
    async def test_handle_agent_request_success(self, mock_request):
        """Test successful agent request handling."""
        with patch("agentuity.server.trace.get_tracer", return_value=MagicMock()) as mock_get_tracer, \
             patch("agentuity.server.extract", return_value={}), \
             patch("agentuity.server.run_agent", new_callable=AsyncMock) as mock_run_agent:
            
            agent_response = MagicMock(spec=AgentResponse)
            agent_response.content_type = "text/plain"
            agent_response.payload = base64.b64encode(b"Test response").decode("utf-8")
            agent_response.metadata = {"key": "value"}
            agent_response.is_stream = False
            mock_run_agent.return_value = agent_response
            
            response = await handle_agent_request(mock_request)
            
            assert response.status == 200
            response_data = json.loads(response.text)
            assert response_data["contentType"] == "text/plain"
            assert response_data["payload"] == base64.b64encode(b"Test response").decode("utf-8")
            assert response_data["metadata"] == {"key": "value"}
            
            mock_get_tracer.assert_called_once_with("http-server")
    
    @pytest.mark.asyncio
    async def test_handle_agent_request_agent_not_found(self, mock_request):
        """Test agent request handling when agent is not found."""
        mock_request.match_info = {"agent_id": "non_existent_agent"}
        
        response = await handle_agent_request(mock_request)
        
        assert response.status == 404
        assert "not found" in response.text
    
    @pytest.mark.asyncio
    async def test_handle_agent_request_invalid_json(self, mock_request):
        """Test agent request handling with invalid JSON."""
        mock_request.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        response = await handle_agent_request(mock_request)
        
        assert response.status == 400
        assert "Invalid JSON" in response.text
    
    @pytest.mark.asyncio
    async def test_handle_agent_request_exception(self, mock_request):
        """Test agent request handling when an exception occurs."""
        with patch("agentuity.server.trace.get_tracer", return_value=MagicMock()), \
             patch("agentuity.server.extract", return_value={}), \
             patch("agentuity.server.run_agent", new_callable=AsyncMock) as mock_run_agent:
            
            mock_run_agent.side_effect = ValueError("Test error")
            
            response = await handle_agent_request(mock_request)
            
            assert response.status == 500
            assert "Test error" in response.text
    
    @pytest.mark.asyncio
    async def test_handle_run_request_success(self, mock_request):
        """Test successful run request handling."""
        mock_request.read = AsyncMock(return_value=b'{"message": "Hello, world!"}')
        
        with patch("agentuity.server.aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"X-Test-Header": "test"}
            mock_response.read = AsyncMock(return_value=json.dumps({
                "contentType": "text/plain",
                "payload": base64.b64encode(b"Test response").decode("utf-8"),
                "metadata": {"key": "value"}
            }).encode())
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            response = await handle_run_request(mock_request)
            
            assert response.status == 200
            assert response.content_type == "text/plain"
            assert response.headers.get("X-Test-Header") == "test"
    
    @pytest.mark.asyncio
    async def test_handle_run_request_client_error(self, mock_request):
        """Test run request handling when a client error occurs."""
        mock_request.read = AsyncMock(return_value=b'{"message": "Hello, world!"}')
        
        with patch("agentuity.server.aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.side_effect = Exception("Test error")
            
            response = await handle_run_request(mock_request)
            
            assert response.status == 500
            response_data = json.loads(response.text)
            assert response_data["error"] == "Internal Server Error"
            assert "Test error" in response_data["details"]
    
    def test_inject_trace_context(self):
        """Test inject_trace_context function."""
        headers = {}
        with patch("agentuity.server.inject") as mock_inject:
            inject_trace_context(headers)
            mock_inject.assert_called_once_with(headers)
    
    def test_inject_trace_context_error(self):
        """Test inject_trace_context handles errors."""
        headers = {}
        with patch("agentuity.server.inject", side_effect=Exception("Test error")), \
             patch("agentuity.server.logger.error") as mock_error:
            inject_trace_context(headers)
            mock_error.assert_called_once()
