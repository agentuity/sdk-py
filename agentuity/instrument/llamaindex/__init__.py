import importlib.util
import logging
import os

logger = logging.getLogger(__name__)


def _patch_openai_client():
    """Patch LlamaIndex OpenAI client to use Agentuity."""
    agentuity_api_key = os.getenv("AGENTUITY_API_KEY") or os.getenv("AGENTUITY_SDK_KEY")
    agentuity_url = os.getenv("AGENTUITY_TRANSPORT_URL", "https://agentuity.ai")

    if not agentuity_api_key:
        logger.debug("No Agentuity API key found, skipping OpenAI client patching")
        return

    # Check if we need to configure (either OPENAI_API_KEY is not set, or it's set to Agentuity key)
    current_openai_key = os.getenv("OPENAI_API_KEY")
    needs_configuration = (
        current_openai_key is None or current_openai_key == agentuity_api_key
    )

    if not needs_configuration:
        logger.debug(
            "OPENAI_API_KEY already set to a different value, skipping Agentuity configuration"
        )
        return

    # Debug logging
    logger.debug("Configuring LlamaIndex OpenAI for Agentuity")
    logger.debug(f"Setting OPENAI_API_KEY to: {agentuity_api_key[:10]}...")
    logger.debug(f"Setting OPENAI_API_BASE to: {agentuity_url}/gateway/openai")

    # Set environment variables that LlamaIndex looks for
    os.environ["OPENAI_API_KEY"] = agentuity_api_key
    os.environ["OPENAI_API_BASE"] = f"{agentuity_url}/gateway/openai"
    # Also set OPENAI_BASE_URL as fallback
    os.environ["OPENAI_BASE_URL"] = f"{agentuity_url}/gateway/openai"

    # Also patch existing OpenAI client classes
    try:
        # Try to find and patch LlamaIndex OpenAI client
        openai_client_class = None

        # Check common locations for OpenAI client
        if importlib.util.find_spec("llama_index.llms.openai"):
            from llama_index.llms.openai import OpenAI

            openai_client_class = OpenAI
            logger.debug("Found OpenAI client in llama_index.llms.openai")
        elif importlib.util.find_spec("llama_index.core.llms.openai"):
            from llama_index.core.llms.openai import OpenAI

            openai_client_class = OpenAI
            logger.debug("Found OpenAI client in llama_index.core.llms.openai")

        if openai_client_class and not hasattr(
            openai_client_class, "_agentuity_patched"
        ):
            original_init = openai_client_class.__init__

            def patched_init(self, *args, **kwargs):
                # Set Agentuity defaults if not provided
                if "api_key" not in kwargs:
                    kwargs["api_key"] = agentuity_api_key
                    logger.debug("Injected Agentuity API key into OpenAI client")
                if "api_base" not in kwargs and "base_url" not in kwargs:
                    # Try both api_base and base_url as different LlamaIndex versions use different names
                    kwargs["api_base"] = f"{agentuity_url}/gateway/openai"
                    logger.debug("Injected Agentuity API base into OpenAI client")
                return original_init(self, *args, **kwargs)

            openai_client_class.__init__ = patched_init
            openai_client_class._agentuity_patched = True
        else:
            logger.debug("OpenAI client class not found or already patched")

    except Exception as e:
        logger.debug(f"Could not patch OpenAI client class: {e}")


def _setup_instrumentation():
    """Set up OpenTelemetry instrumentation for LlamaIndex."""
    try:
        from opentelemetry import trace

        # Try new instrumentation approach first (v0.10.20+)
        try:
            from llama_index.core.instrumentation import get_dispatcher

            class AgentuityEventHandler:
                def __init__(self):
                    self.tracer = trace.get_tracer(__name__)
                    self.spans = {}

                @classmethod
                def class_name(cls) -> str:
                    return "AgentuityEventHandler"

                def handle(self, event, **kwargs) -> None:
                    try:
                        event_id = getattr(event, "id_", str(id(event)))
                        event_type = event.__class__.__name__

                        if "StartEvent" in event_type:
                            span = self.tracer.start_span(
                                f"llamaindex.{event_type}",
                                attributes={"@agentuity/provider": "llamaindex"},
                            )
                            self.spans[event_id] = span
                        elif "EndEvent" in event_type and event_id in self.spans:
                            span = self.spans.pop(event_id)
                            span.set_status(trace.StatusCode.OK)
                            span.end()
                    except Exception as e:
                        logger.debug(f"Event handling error: {e}")

            get_dispatcher().add_event_handler(AgentuityEventHandler())
            return True

        except ImportError:
            # Fallback to legacy approach
            from llama_index.core import set_global_handler

            class AgentuityCallbackHandler:
                def __init__(self):
                    self.tracer = trace.get_tracer(__name__)
                    self.spans = {}

                def on_event_start(
                    self, event_type: str, payload: dict = None, **kwargs
                ) -> str:
                    try:
                        span = self.tracer.start_span(
                            f"llamaindex.{event_type}",
                            attributes={"@agentuity/provider": "llamaindex"},
                        )
                        event_id = str(id(span))
                        self.spans[event_id] = span
                        return event_id
                    except Exception:
                        return ""

                def on_event_end(
                    self,
                    event_type: str,
                    payload: dict = None,
                    event_id: str = None,
                    **kwargs,
                ) -> None:
                    try:
                        if event_id and event_id in self.spans:
                            span = self.spans.pop(event_id)
                            span.set_status(trace.StatusCode.OK)
                            span.end()
                    except Exception:
                        pass

            set_global_handler(AgentuityCallbackHandler())
            return True

    except ImportError:
        logger.debug("OpenTelemetry not available, skipping instrumentation")
        return False


def instrument():
    """Instrument LlamaIndex to work with Agentuity."""
    if not importlib.util.find_spec("llama_index"):
        logger.debug("LlamaIndex not found, skipping instrumentation")
        return False

    if not importlib.util.find_spec("llama_index.core"):
        logger.debug("LlamaIndex core not found, skipping instrumentation")
        return False

    # Configure OpenAI client for LlamaIndex
    _patch_openai_client()

    # Set up instrumentation
    _setup_instrumentation()

    logger.info("Instrumented LlamaIndex Provider to use Agentuity AI Gateway")
    return True
