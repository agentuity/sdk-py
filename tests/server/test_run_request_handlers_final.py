import pytest
import sys
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp.web import Request, Response

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
        response_data = {
            "contentType": "text/plain",
            "payload": base64.b64encode(b"Test response").decode("utf-8"),
            "metadata": {"key": "value"}
        }
        mock_response = Response(
            status=200,
            body=json.dumps(response_data).encode(),
            content_type="application/json"
        )
        
        with patch.object(handle_run_request, "__call__", AsyncMock(return_value=mock_response)):
            response = await handle_run_request(mock_request)
            
            assert response.status == 200
            assert response.content_type == "application/json"
            
            response_json = json.loads(response._body.decode("utf-8"))
            
            assert response_json["contentType"] == "text/plain"
            assert "payload" in response_json
            assert "metadata" in response_json
    
    @pytest.mark.asyncio
    async def test_handle_run_request_client_error(self, mock_request):
        """Test run request handling when a client error occurs."""
        error_data = {
            "error": "Bad Gateway",
            "message": "Error forwarding request",
            "details": "Test error"
        }
        mock_response = Response(
            status=502,
            body=json.dumps(error_data).encode(),
            content_type="application/json"
        )
        
        with patch.object(handle_run_request, "__call__", AsyncMock(return_value=mock_response)):
            response = await handle_run_request(mock_request)
            
            assert response.status == 502
            assert response.content_type == "application/json"
            
            response_json = json.loads(response._body.decode("utf-8"))
            
            assert response_json["error"] == "Bad Gateway"
            assert "Test error" in response_json["details"]
    
    @pytest.mark.asyncio
    async def test_handle_run_request_server_error(self, mock_request):
        """Test run request handling when a server error occurs."""
        error_data = {
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "details": "Test server error"
        }
        mock_response = Response(
            status=500,
            body=json.dumps(error_data).encode(),
            content_type="application/json"
        )
        
        with patch.object(handle_run_request, "__call__", AsyncMock(return_value=mock_response)):
            response = await handle_run_request(mock_request)
            
            assert response.status == 500
            assert response.content_type == "application/json"
            
            response_json = json.loads(response._body.decode("utf-8"))
            
            assert response_json["error"] == "Internal Server Error"
            assert "Test server error" in response_json["details"]
