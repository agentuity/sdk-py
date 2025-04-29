import os
import sys
from unittest.mock import patch, MagicMock
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.http.trace_exporter import Compression

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
            patch("agentuity.otel.TracerProvider") as mock_tracer_provider,
            patch("agentuity.otel.OTLPSpanExporter") as mock_span_exporter,
            patch("agentuity.otel.BatchSpanProcessor"),
            patch("agentuity.otel.trace.set_tracer_provider") as mock_set_tracer,
            patch("agentuity.otel.PeriodicExportingMetricReader"),
            patch("agentuity.otel.OTLPMetricExporter"),
            patch("agentuity.otel.MeterProvider") as mock_meter_provider,
            patch("agentuity.otel.metrics.set_meter_provider") as mock_set_meter,
            patch("agentuity.otel.LoggerProvider") as mock_logger_provider,
            patch("agentuity.otel.BatchLogRecordProcessor"),
            patch("agentuity.otel.OTLPLogExporter"),
            patch("agentuity.otel._logs.set_logger_provider") as mock_set_logger,
            patch("agentuity.otel.LoggingHandler") as mock_logging_handler,
            patch("agentuity.otel.ModuleFilter"),
            patch("agentuity.otel.TraceContextTextMapPropagator"),
            patch("agentuity.otel.set_global_textmap") as mock_set_textmap,
            patch("agentuity.otel.signal.signal") as mock_signal,
            patch("agentuity.otel.openlit.init") as mock_openlit_init,
            patch("agentuity.otel.logger"),
            patch("agentuity.otel.logging.getLogger") as mock_get_logger,
        ):
            mock_root_logger = MagicMock()
            mock_get_logger.return_value = mock_root_logger

            mock_handler_instance = MagicMock()
            mock_logging_handler.return_value = mock_handler_instance

            result = init(config)

            assert result is mock_handler_instance

            mock_tracer_provider.assert_called_once()
            resource_arg = mock_tracer_provider.call_args[1]["resource"]
            assert resource_arg.attributes[SERVICE_NAME] == "test_service"
            assert resource_arg.attributes[SERVICE_VERSION] == "1.0.0"

            mock_span_exporter.assert_called_once_with(
                endpoint="https://test.com/v1/traces",
                headers={"Authorization": "Bearer test_token"},
                compression=Compression.Gzip,
                timeout=10,
            )

            mock_set_tracer.assert_called_once()

            mock_meter_provider.assert_called_once()
            mock_set_meter.assert_called_once()

            mock_logger_provider.assert_called_once()
            mock_set_logger.assert_called_once()

            mock_logging_handler.assert_called_once()
            mock_root_logger.addHandler.assert_called_once_with(mock_handler_instance)

            mock_set_textmap.assert_called_once()

            assert mock_signal.call_count == 2

            mock_openlit_init.assert_called_once()
