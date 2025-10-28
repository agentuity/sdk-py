import logging
import os
import json
from agentuity import __version__
from typing import Optional, Dict, Any
from dataclasses import dataclass
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION
from .logger import create_logger
from .span_patch import patch_span

logger = logging.getLogger(__name__)

patch_span()


@dataclass
class UserOpenTelemetryConfig:
    """Configuration for user-provided OpenTelemetry setup."""
    endpoint: str
    service_name: str
    resource_attributes: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    # Note: Protocol is currently limited to http/protobuf
    # protocol: str = "http/protobuf"
    # sampling_rate: float = 1.0


def parse_user_otel_config() -> Optional[UserOpenTelemetryConfig]:
    """Parse user OTEL configuration from environment variable."""
    raw_config = os.environ.get("AGENTUITY_USER_OTEL_CONF")
    if not raw_config:
        return None
    
    try:
        config_data = json.loads(raw_config)
        
        # Validate required fields
        if not config_data.get("endpoint"):
            logger.warning("User OTEL config missing required 'endpoint' field, ignoring")
            return None
        if not config_data.get("serviceName"):
            logger.warning("User OTEL config missing required 'serviceName' field, ignoring")
            return None
            
        return UserOpenTelemetryConfig(
            endpoint=config_data["endpoint"],
            service_name=config_data["serviceName"],
            resource_attributes=config_data.get("resourceAttributes", {}),
            headers=config_data.get("headers", {})
        )
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid AGENTUITY_USER_OTEL_CONF JSON, ignoring: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error parsing user OTEL config: {e}")
        return None


# Global reference to user logger provider for shutdown
_user_logger_provider = None


def create_user_logger_provider(user_config: UserOpenTelemetryConfig, base_resource_attributes: Dict[str, Any]):
    """Create a user-provided OTLP logger provider."""
    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource
        
        # Merge base resource attributes with user-provided ones
        merged_attributes = {**base_resource_attributes}
        merged_attributes[SERVICE_NAME] = user_config.service_name
        if user_config.resource_attributes:
            merged_attributes.update(user_config.resource_attributes)
        
        resource = Resource.create(merged_attributes)
        
        # Normalize URL - ensure no double slashes
        base_url = user_config.endpoint.rstrip('/')
        logs_url = f"{base_url}/v1/logs"
        
        # Create OTLP exporter
        exporter = OTLPLogExporter(
            endpoint=logs_url,
            headers=user_config.headers or {},
            timeout=10,
        )
        
        # Create batch processor
        processor = BatchLogRecordProcessor(exporter)
        
        # Create logger provider
        provider = LoggerProvider(resource=resource)
        provider.add_log_record_processor(processor)
        
        logger.info(f"User OTLP logger provider initialized for endpoint: {logs_url}")
        
        return {
            "provider": provider,
            "processor": processor,
            "exporter": exporter
        }
        
    except ImportError as e:
        logger.warning(f"OpenTelemetry logs not available for user provider: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to create user logger provider: {e}")
        return None


def init(config: Optional[Dict[str, str]] = None):
    global _user_logger_provider
    
    if config is None:
        config = {}
    
    if os.environ.get("AGENTUITY_OTLP_DISABLED", "false") == "true":
        logger.warning("OTLP disabled, skipping initialization")
        return None

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
        
    # Parse user-provided OTEL configuration
    user_otel_config = parse_user_otel_config()

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
    devmode = (
        config.get("devmode", os.environ.get("AGENTUITY_SDK_DEV_MODE", "false"))
        == "true"
    )
    app_name = config.get(
        "app_name", os.environ.get("AGENTUITY_SDK_APP_NAME", "unknown")
    )
    app_version = config.get(
        "app_version", os.environ.get("AGENTUITY_SDK_APP_VERSION", "unknown")
    )

    # Initialize traceloop for automatic instrumentation
    try:
        from traceloop.sdk import Traceloop

        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}

        resource_attributes = {
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
            "env": "dev" if devmode else "production",
            "version": __version__,
        }

        Traceloop.init(
            app_name=app_name,
            api_endpoint=endpoint,
            headers=headers,
            disable_batch=devmode,
            resource_attributes=resource_attributes,
            telemetry_enabled=False
        )
        logger.debug(f"Traceloop initialized with app_name: {app_name}")
        logger.info("Traceloop configured successfully")
    except ImportError:
        logger.warning("Traceloop not available, skipping automatic instrumentation")
    except Exception as e:
        logger.warning(f"Failed to configure Traceloop: {e}, continuing without it")

    # Initialize user-provided OTEL logger if configured
    if user_otel_config:
        logger.info("Initializing user-provided OTEL configuration")
        _user_logger_provider = create_user_logger_provider(
            user_otel_config, 
            resource_attributes
        )
        if _user_logger_provider:
            # Add the user logger to the multi-delegate system
            from .logger import add_user_logger_provider
            add_user_logger_provider(_user_logger_provider["provider"])

    return None


def shutdown():
    """Shutdown user-provided OTEL resources."""
    global _user_logger_provider
    
    if _user_logger_provider:
        try:
            # Force flush and shutdown the provider
            if hasattr(_user_logger_provider["provider"], "force_flush"):
                _user_logger_provider["provider"].force_flush()
            if hasattr(_user_logger_provider["provider"], "shutdown"):
                _user_logger_provider["provider"].shutdown()
            logger.info("User OTEL logger provider shutdown completed")
        except Exception as e:
            logger.warning(f"Error during user OTEL shutdown: {e}")
        finally:
            _user_logger_provider = None


__all__ = ["init", "create_logger", "shutdown"]
