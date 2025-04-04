import os
import sys
from unittest.mock import patch, MagicMock

sys.modules['openlit'] = MagicMock()

from agentuity.instrument import (  # noqa: E402
    is_module_available,
    check_provider,
    configure_litellm_provider,
    configure_native_provider,
    instrument,
    litellm_providers,
    native_providers
)


class TestInstrumentFunctions:
    """Test suite for the instrument module functions."""
    
    def test_is_module_available_existing(self):
        """Test is_module_available with an existing module."""
        assert is_module_available("os") is True
        
    def test_is_module_available_non_existing(self):
        """Test is_module_available with a non-existing module."""
        assert is_module_available("non_existing_module_123") is False
        
    def test_check_provider_available(self):
        """Test check_provider with an available module."""
        with patch("agentuity.instrument.is_module_available", return_value=True), \
             patch.dict(os.environ, {"TEST_ENV": ""}):
            assert check_provider("test_module", "TEST_ENV") is True
            
    def test_check_provider_not_available(self):
        """Test check_provider with a non-available module."""
        with patch("agentuity.instrument.is_module_available", return_value=False), \
             patch.dict(os.environ, {"TEST_ENV": ""}):
            assert check_provider("test_module", "TEST_ENV") is False
            
    def test_check_provider_env_set(self):
        """Test check_provider with environment variable set."""
        with patch("agentuity.instrument.is_module_available", return_value=True), \
             patch.dict(os.environ, {"TEST_ENV": "value"}):
            assert check_provider("test_module", "TEST_ENV") is False
            
    def test_configure_litellm_provider(self):
        """Test configure_litellm_provider function."""
        test_url = "https://test.com"
        test_api_key = "test_api_key"
        
        original_env = os.environ.copy()
        
        try:
            for provider in litellm_providers:
                name = provider["name"].upper()
                if name + "_API_KEY" in os.environ:
                    del os.environ[name + "_API_KEY"]
                if name + "_API_BASE" in os.environ:
                    del os.environ[name + "_API_BASE"]
            
            result = configure_litellm_provider(test_url, test_api_key)
            
            assert result is True
            
            for provider in litellm_providers:
                name = provider["name"].upper()
                assert os.environ.get(name + "_API_KEY") == test_api_key
                assert os.environ.get(name + "_API_BASE") == test_url + "/gateway/" + provider["provider"]
                
        finally:
            os.environ.clear()
            os.environ.update(original_env)
            
    def test_configure_native_provider(self):
        """Test configure_native_provider function."""
        test_url = "https://test.com"
        test_api_key = "test_api_key"
        
        original_env = os.environ.copy()
        
        try:
            with patch("agentuity.instrument.is_module_available", return_value=True), \
                 patch("agentuity.instrument.logger"):
                
                for provider in native_providers:
                    if provider["env"] in os.environ:
                        del os.environ[provider["env"]]
                    if provider["base"] in os.environ:
                        del os.environ[provider["base"]]
                
                result = configure_native_provider(test_url, test_api_key)
                
                assert result is True
                
                for provider in native_providers:
                    assert os.environ.get(provider["env"]) == test_api_key
                    assert os.environ.get(provider["base"]) == test_url + "/gateway/" + provider["provider"]
                    
        finally:
            os.environ.clear()
            os.environ.update(original_env)
            
    def test_instrument_not_configured(self):
        """Test instrument function when SDK is not configured."""
        original_env = os.environ.copy()
        
        try:
            if "AGENTUITY_TRANSPORT_URL" in os.environ:
                del os.environ["AGENTUITY_TRANSPORT_URL"]
            if "AGENTUITY_API_KEY" in os.environ:
                del os.environ["AGENTUITY_API_KEY"]
            
            with patch("agentuity.instrument.logger") as mock_logger:
                instrument()
                mock_logger.warning.assert_called_once_with("Agentuity SDK not configured")
                
        finally:
            os.environ.clear()
            os.environ.update(original_env)
            
    def test_instrument_configured(self):
        """Test instrument function when SDK is configured."""
        original_env = os.environ.copy()
        
        try:
            os.environ["AGENTUITY_TRANSPORT_URL"] = "https://test.com"
            os.environ["AGENTUITY_API_KEY"] = "test_api_key"
            
            with patch("agentuity.instrument.is_module_available", return_value=False), \
                 patch("agentuity.instrument.configure_litellm_provider", return_value=False), \
                 patch("agentuity.instrument.configure_native_provider", return_value=False), \
                 patch("agentuity.instrument.logger"):
                
                instrument()
                
        finally:
            os.environ.clear()
            os.environ.update(original_env)
