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


litellm_providers = [
    {"name": "anthropic", "provider": "anthropic"},
    {"name": "cohere", "provider": "cohere"},
    {"name": "deepseek", "provider": "deepseek"},
    {"name": "gemini", "provider": "google-ai-studio"},
    {"name": "xai", "provider": "grok"},
    {"name": "groq", "provider": "groq"},
    {"name": "mistral", "provider": "mistral"},
    {"name": "openai", "provider": "openai"},
    {"name": "perplexityai", "provider": "perplexity-ai"},
]


def configure_litellm_provider(agentuity_url: str, agentuity_api_key: str) -> bool:
    ok = False
    for config in litellm_providers:
        name = config["name"].upper()
        envname = name + "_API_KEY"
        if os.getenv(envname, "") == "":
            os.environ[envname] = agentuity_api_key
            os.environ[name + "_API_BASE"] = (
                agentuity_url + "/sdk/gateway/" + config["provider"]
            )
            ok = True
    return ok


native_providers = [
    {
        "env": "OPENAI_API_KEY",
        "base": "OPENAI_BASE_URL",
        "provider": "openai",
        "module": "openai",
    },
    {
        "env": "ANTHROPIC_API_KEY",
        "base": "ANTHROPIC_BASE_URL",
        "provider": "anthropic",
        "module": "anthropic",
    },
    {
        "env": "CO_API_KEY",
        "base": "CO_API_URL",
        "provider": "cohere",
        "module": "cohere",
    },
    {
        "env": "GROQ_API_KEY",
        "base": "GROQ_BASE_URL",
        "provider": "groq",
        "module": "groq",
    },
    # MISTRAL - need to patch _get_url of BaseSDK
    # {
    #     "env": "MISTRAL_API_KEY",
    #     "base": "MISTRAL_BASE_URL",
    #     "provider": "mistral",
    #     "module": "mistralai",
    # },
    # GOOGLE GENAI - need to patch requests and monkey patch the BaseApiClient since they don't expose baseurl env
    # {
    #     "name": "GEMINI_API_KEY",
    #     "provider": "google-ai-studio",
    #     "module": "google-genai",
    # },
]

## TODO: a lot of providers use OpenAI library with their own model and baseurl


def configure_native_provider(agentuity_url: str, agentuity_api_key: str) -> bool:
    ok = False
    for config in native_providers:
        if is_module_available(config["module"]):
            if os.getenv(config["env"], "") == "":
                os.environ[config["env"]] = agentuity_api_key
                os.environ[config["base"]] = (
                    agentuity_url + "/sdk/gateway/" + config["provider"]
                )
                logger.info(
                    "Instrumented %s Provider to use Agentuity AI Gateway",
                    config["provider"],
                )
                ok = True
    return ok


def instrument():
    agentuity_url = os.getenv("AGENTUITY_URL", None)
    agentuity_api_key = os.getenv("AGENTUITY_API_KEY", None)
    agentuity_sdk = agentuity_url is not None and agentuity_api_key is not None
    setupHook = False

    if not agentuity_sdk:
        return

    if is_module_available("litellm"):
        if configure_litellm_provider(agentuity_url, agentuity_api_key):
            logger.info("Instrumented Litellm to use Agentuity AI Gateway")
            setupHook = True

    if configure_native_provider(agentuity_url, agentuity_api_key):
        setupHook = True

    if setupHook and is_module_available("httpx"):
        from agentuity.instrument.httpx_wrap import instrument as instrument_httpx

        instrument_httpx()
