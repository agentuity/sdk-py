import logging
import os
from agentuity import __version__
from typing import Optional, Dict
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION
from .logger import create_logger
from .span_patch import patch_span

logger = logging.getLogger(__name__)

patch_span()


def init(config: Optional[Dict[str, str]] = {}):
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

        # Build app name from project and agent info if available
        project_name = config.get("project_name", "")
        agent_name = config.get("agent_name", "")
        app_name = f"{project_name}:{agent_name}"

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
        )
        logger.debug(f"Traceloop initialized with app_name: {app_name}")
        logger.info("Traceloop configured successfully")
    except ImportError:
        logger.warning("Traceloop not available, skipping automatic instrumentation")
    except Exception as e:
        logger.warning(f"Failed to configure Traceloop: {e}, continuing without it")

    return None


__all__ = ["init", "create_logger"]
