import os
import json
from unittest.mock import patch, MagicMock
from agentuity.otel import (
    parse_user_otel_config, 
    UserOpenTelemetryConfig,
    create_user_logger_provider,
    shutdown
)


class TestUserOtelConfig:
    """Test user-provided OpenTelemetry configuration."""

    def test_parse_user_otel_config_none(self):
        """Test parsing when no config is provided."""
        # Ensure env var is not set
        if "AGENTUITY_USER_OTEL_CONF" in os.environ:
            del os.environ["AGENTUITY_USER_OTEL_CONF"]
        
        result = parse_user_otel_config()
        assert result is None

    def test_parse_user_otel_config_valid(self):
        """Test parsing valid user OTEL configuration."""
        test_config = {
            "endpoint": "https://my-otel.example.com",
            "serviceName": "my-test-service",
            "resourceAttributes": {
                "service.version": "1.0.0",
                "environment": "test"
            },
            "headers": {
                "authorization": "Bearer test-token"
            }
        }
        
        os.environ["AGENTUITY_USER_OTEL_CONF"] = json.dumps(test_config)
        
        try:
            result = parse_user_otel_config()
            assert result is not None
            assert isinstance(result, UserOpenTelemetryConfig)
            assert result.endpoint == test_config["endpoint"]
            assert result.service_name == test_config["serviceName"]
            assert result.resource_attributes == test_config["resourceAttributes"]
            assert result.headers == test_config["headers"]
        finally:
            del os.environ["AGENTUITY_USER_OTEL_CONF"]

    def test_parse_user_otel_config_invalid_json(self):
        """Test parsing with invalid JSON."""
        os.environ["AGENTUITY_USER_OTEL_CONF"] = "invalid json"
        
        try:
            result = parse_user_otel_config()
            assert result is None
        finally:
            del os.environ["AGENTUITY_USER_OTEL_CONF"]

    def test_parse_user_otel_config_missing_endpoint(self):
        """Test parsing with missing required endpoint field."""
        incomplete_config = {
            "serviceName": "my-service"
        }
        
        os.environ["AGENTUITY_USER_OTEL_CONF"] = json.dumps(incomplete_config)
        
        try:
            result = parse_user_otel_config()
            assert result is None
        finally:
            del os.environ["AGENTUITY_USER_OTEL_CONF"]

    def test_parse_user_otel_config_missing_service_name(self):
        """Test parsing with missing required serviceName field."""
        incomplete_config = {
            "endpoint": "https://example.com"
        }
        
        os.environ["AGENTUITY_USER_OTEL_CONF"] = json.dumps(incomplete_config)
        
        try:
            result = parse_user_otel_config()
            assert result is None
        finally:
            del os.environ["AGENTUITY_USER_OTEL_CONF"]

    def test_parse_user_otel_config_minimal_valid(self):
        """Test parsing with minimal valid configuration."""
        minimal_config = {
            "endpoint": "https://example.com",
            "serviceName": "test-service"
        }
        
        os.environ["AGENTUITY_USER_OTEL_CONF"] = json.dumps(minimal_config)
        
        try:
            result = parse_user_otel_config()
            assert result is not None
            assert result.endpoint == minimal_config["endpoint"]
            assert result.service_name == minimal_config["serviceName"]
            assert result.resource_attributes == {}  # Default empty dict
            assert result.headers == {}  # Default empty dict
        finally:
            del os.environ["AGENTUITY_USER_OTEL_CONF"]

    @patch('agentuity.otel.logger')
    def test_parse_user_otel_config_exception_handling(self, mock_logger):
        """Test that unexpected exceptions are handled gracefully."""
        os.environ["AGENTUITY_USER_OTEL_CONF"] = "valid json but will cause error"
        
        with patch('json.loads', side_effect=KeyError("test error")):
            try:
                result = parse_user_otel_config()
                assert result is None
                mock_logger.warning.assert_called_once()
            finally:
                del os.environ["AGENTUITY_USER_OTEL_CONF"]


class TestCreateUserLoggerProvider:
    """Test user logger provider creation."""

    def test_create_user_logger_provider_import_error(self):
        """Test behavior when OpenTelemetry logs are not available."""
        user_config = UserOpenTelemetryConfig(
            endpoint="https://example.com",
            service_name="test-service"
        )
        base_attributes = {"test": "value"}
        
        with patch('agentuity.otel.logger') as mock_logger:
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                result = create_user_logger_provider(user_config, base_attributes)
                assert result is None
                mock_logger.warning.assert_called_once()

    @patch('agentuity.otel.logger')
    def test_create_user_logger_provider_success(self, mock_logger):
        """Test successful creation of user logger provider."""
        user_config = UserOpenTelemetryConfig(
            endpoint="https://example.com/",  # Test URL normalization
            service_name="test-service",
            resource_attributes={"custom": "attr"},
            headers={"auth": "token"}
        )
        base_attributes = {"service.name": "base-service", "version": "1.0"}
        
        # Mock the OpenTelemetry imports
        mock_exporter = MagicMock()
        mock_processor = MagicMock()
        mock_provider = MagicMock()
        mock_resource = MagicMock()
        
        with patch('opentelemetry.exporter.otlp.proto.http._log_exporter.OTLPLogExporter', return_value=mock_exporter) as mock_exp_cls:
            with patch('opentelemetry.sdk._logs.export.BatchLogRecordProcessor', return_value=mock_processor):
                with patch('opentelemetry.sdk._logs.LoggerProvider', return_value=mock_provider):
                    with patch('opentelemetry.sdk.resources.Resource.create', return_value=mock_resource) as mock_res_create:
                        result = create_user_logger_provider(user_config, base_attributes)
                        
                        # Verify the result structure
                        assert result is not None
                        assert result["provider"] == mock_provider
                        assert result["processor"] == mock_processor
                        assert result["exporter"] == mock_exporter
                        
                        # Verify URL normalization (trailing slash removed)
                        mock_exp_cls.assert_called_once_with(
                            endpoint="https://example.com/v1/logs",
                            headers={"auth": "token"},
                            timeout=10
                        )
                        
                        # Verify resource creation with merged attributes
                        expected_attributes = {
                            "service.name": "test-service",  # Should override base
                            "version": "1.0",
                            "custom": "attr"
                        }
                        mock_res_create.assert_called_once_with(expected_attributes)
                        
                        # Verify provider setup
                        mock_provider.add_log_record_processor.assert_called_once_with(mock_processor)
                        
                        # Verify info log
                        mock_logger.info.assert_called_once()


class TestShutdown:
    """Test shutdown functionality."""

    def test_shutdown_no_provider(self):
        """Test shutdown when no user provider exists."""
        # Ensure global provider is None
        import agentuity.otel
        agentuity.otel._user_logger_provider = None
        
        # Should not raise any errors
        shutdown()

    @patch('agentuity.otel.logger')
    def test_shutdown_with_provider(self, mock_logger):
        """Test shutdown with user provider."""
        import agentuity.otel
        
        mock_provider = MagicMock()
        mock_processor = MagicMock()
        mock_exporter = MagicMock()
        
        agentuity.otel._user_logger_provider = {
            "provider": mock_provider,
            "processor": mock_processor,
            "exporter": mock_exporter
        }
        
        try:
            shutdown()
            
            # Verify all components had their shutdown methods called
            mock_provider.force_flush.assert_called_once()
            mock_provider.shutdown.assert_called_once()
            mock_processor.force_flush.assert_called_once()
            mock_processor.shutdown.assert_called_once()
            mock_exporter.force_flush.assert_called_once()
            mock_exporter.shutdown.assert_called_once()
            
            # Verify provider was cleared
            assert agentuity.otel._user_logger_provider is None
            
            # Verify info log
            mock_logger.info.assert_called_once()
        finally:
            # Clean up
            agentuity.otel._user_logger_provider = None

    @patch('agentuity.otel.logger')
    def test_shutdown_with_provider_error(self, mock_logger):
        """Test shutdown when provider methods raise errors."""
        import agentuity.otel
        
        mock_provider = MagicMock()
        mock_processor = MagicMock()
        mock_exporter = MagicMock()
        
        # Make various methods raise errors to test error handling
        mock_provider.force_flush.side_effect = Exception("Provider flush error")
        mock_processor.shutdown.side_effect = Exception("Processor shutdown error")
        mock_exporter.close.side_effect = Exception("Exporter close error")
        
        agentuity.otel._user_logger_provider = {
            "provider": mock_provider,
            "processor": mock_processor,
            "exporter": mock_exporter
        }
        
        try:
            shutdown()
            
            # Verify provider was still cleared despite errors
            assert agentuity.otel._user_logger_provider is None
            
            # Verify warning was logged for each error (3 total)
            assert mock_logger.warning.call_count == 3
            
            # Verify the specific error messages
            warning_calls = [call.args[0] for call in mock_logger.warning.call_args_list]
            assert any("Provider flush error" in msg for msg in warning_calls)
            assert any("Processor shutdown error" in msg for msg in warning_calls)
            assert any("Exporter close error" in msg for msg in warning_calls)
        finally:
            # Clean up
            agentuity.otel._user_logger_provider = None

    @patch('agentuity.otel.logger')
    def test_shutdown_provider_missing_methods(self, mock_logger):
        """Test shutdown when components don't have expected methods."""
        import agentuity.otel
        
        mock_provider = MagicMock()
        mock_processor = MagicMock()
        mock_exporter = MagicMock()
        
        # Remove some methods to simulate components without them
        del mock_provider.force_flush
        del mock_processor.shutdown
        del mock_exporter.close
        
        agentuity.otel._user_logger_provider = {
            "provider": mock_provider,
            "processor": mock_processor,
            "exporter": mock_exporter
        }
        
        try:
            shutdown()
            
            # Should not call the missing methods and not raise errors
            assert not hasattr(mock_provider, 'force_flush')
            assert not hasattr(mock_processor, 'shutdown')
            assert not hasattr(mock_exporter, 'close')
            
            # But should call the methods that do exist
            mock_provider.shutdown.assert_called_once()
            mock_processor.force_flush.assert_called_once()
            mock_exporter.force_flush.assert_called_once()
            mock_exporter.shutdown.assert_called_once()
            
            # Verify provider was cleared
            assert agentuity.otel._user_logger_provider is None
            
            # Should log info (successful shutdown)
            mock_logger.info.assert_called_once()
        finally:
            # Clean up
            agentuity.otel._user_logger_provider = None

    @patch('agentuity.otel.logger')
    def test_shutdown_comprehensive_component_handling(self, mock_logger):
        """Test shutdown handles all methods (force_flush, shutdown, close) for all components."""
        import agentuity.otel
        
        mock_provider = MagicMock()
        mock_processor = MagicMock()
        mock_exporter = MagicMock()
        
        agentuity.otel._user_logger_provider = {
            "provider": mock_provider,
            "processor": mock_processor,
            "exporter": mock_exporter
        }
        
        try:
            shutdown()
            
            # Verify all methods called on all components
            for component in [mock_provider, mock_processor, mock_exporter]:
                component.force_flush.assert_called_once()
                component.shutdown.assert_called_once()
                component.close.assert_called_once()
            
            # Verify provider was cleared
            assert agentuity.otel._user_logger_provider is None
            
            # Should log info (successful shutdown)
            mock_logger.info.assert_called_once()
        finally:
            # Clean up
            agentuity.otel._user_logger_provider = None
