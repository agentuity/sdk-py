import sys
from unittest.mock import patch, MagicMock
import httpx
from agentuity import __version__

sys.modules['openlit'] = MagicMock()

from agentuity.instrument.httpx_wrap import gateway_urls  # noqa: E402


class TestHttpxWrap:
    """Test suite for the httpx_wrap module."""
    
    def test_gateway_urls_content(self):
        """Test that gateway_urls contains expected values."""
        assert "https://api.agentuity.com/sdk/gateway/" in gateway_urls
        assert "https://agentuity.ai/gateway/" in gateway_urls
        assert "https://api.agentuity.dev/" in gateway_urls
        assert "http://localhost:" in gateway_urls
    
    def test_instrument_calls_patch_function_wrapper(self):
        """Test that instrument calls wrapt.patch_function_wrapper."""
        with patch('wrapt.patch_function_wrapper') as mock_patch:
            from agentuity.instrument.httpx_wrap import instrument
            
            instrument()
            
            mock_patch.assert_called_once_with(httpx.Client, "send")
    
    def test_wrapped_request_functionality(self):
        """Test the functionality of the wrapped_request function."""
        def test_wrapped_request(request, api_key):
            url = str(request.url)
            if any(gateway_url in url for gateway_url in gateway_urls):
                request.headers["Authorization"] = f"Bearer {api_key}"
                request.headers["User-Agent"] = f"Agentuity Python SDK/{__version__}"
            return request
        
        gateway_request = MagicMock()
        gateway_request.url = "https://api.agentuity.com/sdk/gateway/v1/completions"
        gateway_request.headers = {}
        
        result = test_wrapped_request(gateway_request, "test_api_key")
        assert "Authorization" in result.headers
        assert result.headers["Authorization"] == "Bearer test_api_key"
        assert "User-Agent" in result.headers
        assert result.headers["User-Agent"] == f"Agentuity Python SDK/{__version__}"
        
        non_gateway_request = MagicMock()
        non_gateway_request.url = "https://example.com/api"
        non_gateway_request.headers = {}
        
        result = test_wrapped_request(non_gateway_request, "test_api_key")
        assert "Authorization" not in result.headers
        assert "User-Agent" not in result.headers
