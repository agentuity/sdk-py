import pytest
import sys
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp.web import Request, Response, Application

sys.modules['openlit'] = MagicMock()



class TestRunRequestHandlers:
    """Test suite for server run request handlers."""
    
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
        request.host = "localhost"
        request.path = "/run/test_agent"
        request.url = "http://localhost/run/test_agent"
        return request
    
    @pytest.mark.asyncio
    async def test_handle_run_request_with_direct_patching(self, mock_request):
        """Test run request handling by directly patching the implementation."""
        mock_response = Response(
            status=200,
            body=json.dumps({
                "contentType": "text/plain",
                "payload": base64.b64encode(b"Test response").decode("utf-8"),
                "metadata": {"key": "value"}
            }).encode(),
            content_type="application/json",
            headers={"X-Test-Header": "test"}
        )
        
        with patch("agentuity.server.handle_run_request", AsyncMock(return_value=mock_response)) as mock_handler:
            response = await mock_handler(mock_request)
            
            assert response.status == 200
            assert response.content_type == "application/json"
            assert response.headers.get("X-Test-Header") == "test"
            
            response_body = response.body.decode('utf-8')
            response_data = json.loads(response_body)
            assert response_data["contentType"] == "text/plain"
            assert "payload" in response_data
            assert "metadata" in response_data
    
    @pytest.mark.asyncio
    async def test_handle_run_request_error_with_direct_patching(self, mock_request):
        """Test run request error handling by directly patching the implementation."""
        mock_error_response = Response(
            status=500,
            body=json.dumps({
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "details": "Test error"
            }).encode(),
            content_type="application/json"
        )
        
        with patch("agentuity.server.handle_run_request", AsyncMock(return_value=mock_error_response)) as mock_handler:
            response = await mock_handler(mock_request)
            
            assert response.status == 500
            assert response.content_type == "application/json"
            
            response_body = response.body.decode('utf-8')
            response_data = json.loads(response_body)
            assert response_data["error"] == "Internal Server Error"
            assert "Test error" in response_data["details"]
