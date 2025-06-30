import logging
import os
from agentuity import __version__

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None

try:
    import wrapt
except ImportError:
    wrapt = None

try:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
except ImportError:
    HTTPXClientInstrumentor = None

gateway_urls = [
    "https://api.agentuity.com/sdk/gateway/",
    "https://agentuity.ai/gateway/",
    "https://api.agentuity.dev/",
    "http://localhost:",
]


def instrument():
    """Instrument httpx to work with Agentuity."""
    if httpx is None:
        logger.error("Could not instrument httpx: No module named 'httpx'")
        return False

    if wrapt is None:
        logger.error("Could not instrument httpx: No module named 'wrapt'")
        return False

    if HTTPXClientInstrumentor is None:
        logger.error(
            "Could not instrument httpx: No module named 'opentelemetry.instrumentation.httpx'"
        )
        return False

    try:
        HTTPXClientInstrumentor().instrument()

        @wrapt.patch_function_wrapper(httpx.Client, "send")
        def wrapped_request(wrapped, instance, args, kwargs):
            request = args[0] if args else kwargs.get("request")
            url = str(request.url)
            if any(gateway_url in url for gateway_url in gateway_urls):
                agentuity_api_key = os.getenv("AGENTUITY_API_KEY", None) or os.getenv(
                    "AGENTUITY_SDK_KEY", None
                )
                request.headers["Authorization"] = f"Bearer {agentuity_api_key}"
                request.headers["User-Agent"] = f"Agentuity Python SDK/{__version__}"
            return wrapped(*args, **kwargs)

        logger.info("Configured httpx to work with Agentuity")
        return True

    except Exception as e:
        logger.error(f"Error instrumenting httpx: {str(e)}")
        return False
