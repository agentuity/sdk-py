import os
import sys
from unittest.mock import patch, MagicMock
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION


sys.modules["openlit"] = MagicMock()
from agentuity.otel import init  # noqa: E402


class TestOtelInit:
    """Test suite for the OpenTelemetry initialization module."""

    def test_init_disabled(self):
        """Test init when OTLP is disabled."""
        mock_logger = MagicMock()
        with (
            patch.dict(os.environ, {"AGENTUITY_OTLP_DISABLED": "true"}),
            patch("agentuity.otel.logger", mock_logger),
        ):
            result = init()
            assert result is None
            mock_logger.warning.assert_called_once_with(
                "OTLP disabled, skipping initialization"
            )

    def test_init_no_endpoint(self):
        """Test init when no endpoint is provided."""
        mock_logger = MagicMock()
        with (
            patch.dict(os.environ, {"AGENTUITY_OTLP_DISABLED": "false"}),
            patch("agentuity.otel.logger", mock_logger),
        ):
            if "AGENTUITY_OTLP_URL" in os.environ:
                del os.environ["AGENTUITY_OTLP_URL"]

            result = init({})
            assert result is None
            mock_logger.warning.assert_called_once_with(
                "No endpoint found, skipping OTLP initialization"
            )

    def test_init_no_bearer_token(self):
        """Test init when no bearer token is provided."""
        mock_logger = MagicMock()
        with (
            patch.dict(
                os.environ,
                {
                    "AGENTUITY_OTLP_DISABLED": "false",
                    "AGENTUITY_OTLP_URL": "https://test.com",
                },
            ),
            patch("agentuity.otel.logger", mock_logger),
        ):
            if "AGENTUITY_OTLP_BEARER_TOKEN" in os.environ:
                del os.environ["AGENTUITY_OTLP_BEARER_TOKEN"]

            result = init({})
            assert result is None
            mock_logger.warning.assert_called_once_with(
                "No bearer token found, skipping OTLP initialization"
            )

    def test_init_with_config(self):
        """Test init with valid configuration."""
        config = {
            "endpoint": "https://test.com",
            "bearer_token": "test_token",
            "service_name": "test_service",
            "service_version": "1.0.0",
        }

        with (
            patch("traceloop.sdk.Traceloop.init") as mock_traceloop_init,
            patch("agentuity.otel.logger"),
        ):
            result = init(config)

            assert result is None

            mock_traceloop_init.assert_called_once()
            args, kwargs = mock_traceloop_init.call_args
            assert kwargs["api_endpoint"] == "https://test.com"
            assert kwargs["headers"] == {"Authorization": "Bearer test_token"}
            assert kwargs["resource_attributes"][SERVICE_NAME] == "test_service"
            assert kwargs["resource_attributes"][SERVICE_VERSION] == "1.0.0"
