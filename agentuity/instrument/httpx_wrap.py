import os
import httpx
import wrapt


def instrument():
    # Patch the httpx.Client.send method to add the
    # Agentuity API key to the request headers
    @wrapt.patch_function_wrapper(httpx.Client, "send")
    def wrapped_request(wrapped, instance, args, kwargs):
        request = args[0] if args else kwargs.get("request")
        agentuity_api_key = os.getenv("AGENTUITY_API_KEY", None)
        request.headers["Authorization"] = f"Bearer {agentuity_api_key}"
        return wrapped(*args, **kwargs)
