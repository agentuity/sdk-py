import pytest
import os
import httpx
from unittest.mock import patch, MagicMock
import sys
from agentuity import __version__

sys.modules['openlit'] = MagicMock()

from agentuity.instrument.httpx_wrap import instrument, gateway_urls  # noqa: E402


class TestHttpxWrap:
    """Test suite for the httpx_wrap module."""
    
    def test_instrument_adds_auth_header(self):
        """Test that instrument adds auth header to requests to gateway URLs."""
        mock_request = MagicMock()
        mock_request.url = "https://api.agentuity.com/sdk/gateway/v1/completions"
        mock_request.headers = {}
        
        mock_wrapped = MagicMock(return_value="test_response")
        
        with patch.dict(os.environ, {"AGENTUITY_API_KEY": "test_api_key"}):
            with patch('wrapt.patch_function_wrapper') as mock_patch:
                instrument()
                wrapper_fn = mock_patch.call_args[0][2]
                
                result = wrapper_fn(mock_wrapped, None, [mock_request], {})
                
                assert result == "test_response"
                assert "Authorization" in mock_request.headers
                assert mock_request.headers["Authorization"] == "Bearer test_api_key"
                assert "User-Agent" in mock_request.headers
                assert mock_request.headers["User-Agent"] == f"Agentuity Python SDK/{__version__}"
    
    def test_instrument_ignores_non_gateway_urls(self):
        """Test that instrument doesn't add auth header to non-gateway URLs."""
        mock_request = MagicMock()
        mock_request.url = "https://example.com/api"
        mock_request.headers = {}
        
        mock_wrapped = MagicMock(return_value="test_response")
        
        with patch.dict(os.environ, {"AGENTUITY_API_KEY": "test_api_key"}):
            with patch('wrapt.patch_function_wrapper') as mock_patch:
                instrument()
                wrapper_fn = mock_patch.call_args[0][2]
                
                result = wrapper_fn(mock_wrapped, None, [mock_request], {})
                
                assert result == "test_response"
                assert "Authorization" not in mock_request.headers
                assert "User-Agent" not in mock_request.headers
    
    def test_gateway_urls_content(self):
        """Test that gateway_urls contains expected values."""
        assert "https://api.agentuity.com/sdk/gateway/" in gateway_urls
        assert "https://agentuity.ai/gateway/" in gateway_urls
        assert "https://api.agentuity.dev/" in gateway_urls
        assert "http://localhost:" in gateway_urls
