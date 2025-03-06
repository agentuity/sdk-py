import importlib.util
import logging
import os

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


def check_provider(module_name: str, env: str) -> bool:
    if is_module_available(module_name) and os.getenv(env, "") == "":
        return True
    return False


def instrument():
    agentuity_url = os.getenv("AGENTUITY_URL", None)
    agentuity_api_key = os.getenv("AGENTUITY_API_KEY", None)
    agentuity_sdk = agentuity_url is not None and agentuity_api_key is not None

    if agentuity_sdk and check_provider("openai", "OPENAI_API_KEY"):
        # doesn't matter the value but it must be set
        os.environ["OPENAI_API_KEY"] = "x"
        # point to the agentuity AI gateway as the base URL
        url = agentuity_url + "/sdk/gateway/openai"
        # this is used by the openai library
        os.environ["OPENAI_BASE_URL"] = url
        # this is used by the litellm library
        os.environ["OPENAI_API_BASE"] = url
        logger.info("Instrumented OpenAI to use Agentuity AI Gateway")
        setupHook = True

    if setupHook and is_module_available("httpx"):
        from agentuity.instrument.httpx_wrap import instrument as instrument_httpx

        instrument_httpx()
