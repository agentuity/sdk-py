import os
import httpx
import wrapt
from agentuity import __version__
# from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
# from agentuity.otel import trace_provider

gateway_urls = [
    "https://api.agentuity.com/sdk/gateway/",
    "https://agentuity.ai/gateway/",
    "https://api.agentuity.dev/",
    "http://localhost:",
]


def instrument():
    # HTTPXClientInstrumentor().instrument(tracer_provider=trace_provider)

    # Patch the httpx.Client.send method to add the
    # Agentuity API key to the request headers
    @wrapt.patch_function_wrapper(httpx.Client, "send")
    def wrapped_request(wrapped, instance, args, kwargs):
        request = args[0] if args else kwargs.get("request")
        url = str(request.url)
        if any(gateway_url in url for gateway_url in gateway_urls):
            agentuity_api_key = os.getenv("AGENTUITY_API_KEY", None)
            request.headers["Authorization"] = f"Bearer {agentuity_api_key}"
            request.headers["User-Agent"] = f"Agentuity Python SDK/{__version__}"
        return wrapped(*args, **kwargs)
