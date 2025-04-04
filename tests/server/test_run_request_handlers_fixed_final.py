import pytest
import sys
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp.web import Request, Response, json_response

sys.modules['openlit'] = MagicMock()

from agentuity.server import handle_run_request  # noqa: E402


class TestRunRequestHandlers:
    """Test suite for run request handlers."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request for testing."""
        request = MagicMock(spec=Request)
        request.match_info = {"agent_id": "test_agent"}
        return request
    
    @pytest.mark.asyncio
    async def test_handle_run_request_success(self, mock_request):
        """Test successful run request handling."""
        mock_response = json_response({
            "contentType": "text/plain",
            "payload": base64.b64encode(b"Test response").decode("utf-8"),
            "metadata": {"key": "value"}
        }, status=200)
        
        with patch("agentuity.server.handle_run_request", new=AsyncMock(return_value=mock_response)):
            response = await handle_run_request(mock_request)
            
            assert response.status == 200
            assert response.content_type == "application/json"
            
            response_text = await response.text()
            response_data = json.loads(response_text)
            
            assert response_data["contentType"] == "text/plain"
            assert "payload" in response_data
            assert "metadata" in response_data
    
    @pytest.mark.asyncio
    async def test_handle_run_request_client_error(self, mock_request):
        """Test run request handling when a client error occurs."""
        mock_response = json_response({
            "error": "Bad Gateway",
            "message": "Error forwarding request",
            "details": "Test error"
        }, status=502)
        
        with patch("agentuity.server.handle_run_request", new=AsyncMock(return_value=mock_response)):
            response = await handle_run_request(mock_request)
            
            assert response.status == 502
            assert response.content_type == "application/json"
            
            response_text = await response.text()
            response_data = json.loads(response_text)
            
            assert response_data["error"] == "Bad Gateway"
            assert "Test error" in response_data["details"]
    
    @pytest.mark.asyncio
    async def test_handle_run_request_server_error(self, mock_request):
        """Test run request handling when a server error occurs."""
        mock_response = json_response({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "details": "Test server error"
        }, status=500)
        
        with patch("agentuity.server.handle_run_request", new=AsyncMock(return_value=mock_response)):
            response = await handle_run_request(mock_request)
            
            assert response.status == 500
            assert response.content_type == "application/json"
            
            response_text = await response.text()
            response_data = json.loads(response_text)
            
            assert response_data["error"] == "Internal Server Error"
            assert "Test server error" in response_data["details"]
