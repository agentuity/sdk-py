import logging
import signal
import os
from agentuity import __version__
from typing import Optional, Dict
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import Compression
from opentelemetry import _logs
from opentelemetry.sdk._logs import LoggingHandler, LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from .propagator import AgentuityPropagator
from .logfilter import ModuleFilter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


logger = logging.getLogger(__name__)


def init(config: Optional[Dict[str, str]] = {}):
    endpoint = config.get("endpoint", os.environ.get("AGENTUITY_OTLP_URL"))
    if endpoint is None:
        logger.warning("No endpoint found, skipping OTLP initialization")
        return None

    bearer_token = config.get(
        "bearer_token", os.environ.get("AGENTUITY_OTLP_BEARER_TOKEN")
    )
    if bearer_token is None:
        logger.warning("No bearer token found, skipping OTLP initialization")
        return None

    orgId = config.get("orgId", os.environ.get("AGENTUITY_CLOUD_ORG_ID", "unknown"))
    projectId = config.get(
        "projectId", os.environ.get("AGENTUITY_CLOUD_PROJECT_ID", "unknown")
    )
    deploymentId = config.get(
        "deploymentId", os.environ.get("AGENTUITY_CLOUD_DEPLOYMENT_ID", "unknown")
    )
    cliVersion = config.get(
        "cliVersion", os.environ.get("AGENTUITY_CLI_VERSION", "unknown")
    )
    sdkVersion = __version__
    environment = config.get(
        "environment", os.environ.get("AGENTUITY_ENVIRONMENT", "development")
    )
    devmode = config.get("devmode", os.environ.get("AGENTUITY_SDK_DEV_MODE", "false"))
    app_name = config.get(
        "app_name", os.environ.get("AGENTUITY_SDK_APP_NAME", "unknown")
    )
    app_version = config.get(
        "app_version", os.environ.get("AGENTUITY_SDK_APP_VERSION", "unknown")
    )
    export_internal_ms = 1000 if devmode else 60000

    resource = Resource(
        attributes={
            SERVICE_NAME: config.get(
                "service_name",
                app_name,
            ),
            SERVICE_VERSION: config.get(
                "service_version",
                app_version,
            ),
            "@agentuity/orgId": orgId,
            "@agentuity/projectId": projectId,
            "@agentuity/deploymentId": deploymentId,
            "@agentuity/env": environment,
            "@agentuity/devmode": devmode,
            "@agentuity/sdkVersion": sdkVersion,
            "@agentuity/cliVersion": cliVersion,
            "@agentuity/language": "python",
        }
    )

    headers = {
        "Authorization": "Bearer " + bearer_token,
    }

    tracerProvider = TracerProvider(
        resource=resource,
        shutdown_on_exit=False,
    )
    processor = BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=endpoint + "/v1/traces",
            headers=headers,
            compression=Compression.Gzip,
            timeout=10,
        ),
        export_timeout_millis=export_internal_ms,
    )
    tracerProvider.add_span_processor(processor)
    trace.set_tracer_provider(tracerProvider)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=endpoint + "/v1/metrics",
            headers=headers,
            compression=Compression.Gzip,
            timeout=10,
        ),
        export_interval_millis=export_internal_ms,
    )
    meterProvider = MeterProvider(
        resource=resource,
        metric_readers=[reader],
        shutdown_on_exit=False,
    )
    metrics.set_meter_provider(meterProvider)

    # Set up logging
    loggerProvider = LoggerProvider(resource=resource)
    logProcessor = BatchLogRecordProcessor(
        OTLPLogExporter(
            endpoint=endpoint + "/v1/logs",
            headers=headers,
            compression=Compression.Gzip,
            timeout=10,
        ),
        max_export_batch_size=512,
        export_timeout_millis=export_internal_ms,
    )
    loggerProvider.add_log_record_processor(logProcessor)
    _logs.set_logger_provider(loggerProvider)

    handler = LoggingHandler(
        level=logging.NOTSET,
        logger_provider=loggerProvider,
    )
    module_filter = ModuleFilter()
    handler.addFilter(module_filter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    propagator = CompositePropagator(
        [
            AgentuityPropagator(),
            TraceContextTextMapPropagator(),
        ]
    )
    set_global_textmap(propagator)

    stopped = False

    def signal_handler(sig, frame):
        nonlocal stopped
        if stopped:
            return
        stopped = True
        logProcessor.force_flush()
        meterProvider.force_flush()
        tracerProvider.force_flush()
        meterProvider.shutdown()
        tracerProvider.shutdown()
        logProcessor.shutdown()

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return handler
