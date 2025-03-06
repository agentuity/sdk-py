import importlib.util
import logging
import os
from agentuity.instrument.requests_wrap import register_pre_post_hook

logger = logging.getLogger(__name__)


def is_module_available(module_name: str) -> bool:
    """
    Check if a module is available without importing it.

    Args:
        module_name: The name of the module to check

    Returns:
        bool: True if the module can be imported, False otherwise
    """
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


hook_request_post = False
agentuity_url = None
agentuity_api_key = None


def instrument():
    global hook_request_post
    global agentuity_url
    global agentuity_api_key

    agentuity_url = os.getenv("AGENTUITY_URL", None)
    agentuity_api_key = os.getenv("AGENTUITY_API_KEY", None)
    agentuity_sdk = agentuity_url is not None and agentuity_api_key is not None

    openai_key_defined = os.getenv("OPENAI_API_KEY", None) is not None
    # only hook if we don't have environment variable set
    hook_openai = openai_key_defined is not True

    hook_request_post = agentuity_sdk is True and (
        is_module_available("litellm") or is_module_available("openai")
    )

    if hook_request_post and hook_openai:
        # doesn't matter the value but it must be set
        os.environ["OPENAI_API_KEY"] = "x"
        # point to the agentuity AI gateway as the base URL
        os.environ["OPENAI_API_BASE"] = agentuity_url + "/sdk/gateway/openai"
        logger.info("Instrumented OpenAI to use Agentuity AI Gateway")


# Define a pre-request hook for hooking into the outgoing requests
# to add the agentuity authorization header
@register_pre_post_hook
def log_request(url, kwargs):
    if not hook_request_post:
        return url, kwargs

    if agentuity_url not in url:
        return url, kwargs

    if "/sdk/gateway/" not in url:
        return url, kwargs

    headers = kwargs.get("headers", {})
    if not isinstance(headers, dict):
        headers = {}

    # add our API Key
    headers["Authorization"] = f"Bearer {agentuity_api_key}"

    logger.debug(
        f"PRE-HOOK: About to make a POST request to {url}, added agentuity authorization header"
    )

    return url, kwargs
