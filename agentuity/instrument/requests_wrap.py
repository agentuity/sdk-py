import wrapt
import requests
import logging

# Hook functions that will be called before and after the POST requests
_pre_post_hooks = []
_post_post_hooks = []

logger = logging.getLogger(__name__)


def register_pre_post_hook(hook_func):
    """
    Register a function to be called before a POST request is made.

    The hook function should accept the following parameters:
    - url: The URL for the request
    - kwargs: The keyword arguments passed to the request function

    The hook can modify the kwargs dictionary to change the request parameters.
    It should return a tuple of (url, kwargs).
    """
    # Check if a hook with the same name is already registered
    hook_name = hook_func.__name__
    for hook in _pre_post_hooks:
        if hook.__name__ == hook_name:
            logger.debug(f"Hook {hook_name} already registered, skipping")
            return hook_func

    _pre_post_hooks.append(hook_func)
    return hook_func


def register_post_post_hook(hook_func):
    """
    Register a function to be called after a POST request is made.

    The hook function should accept the following parameters:
    - url: The URL for the request
    - kwargs: The keyword arguments passed to the request function
    - response: The response object returned by the request

    The hook can inspect or modify the response before it's returned.
    It should return the response object.
    """
    _post_post_hooks.append(hook_func)
    return hook_func


def _apply_pre_hooks(url, kwargs):
    """Apply all pre-request hooks in order."""
    for hook in _pre_post_hooks:
        url, kwargs = hook(url, kwargs)
    return url, kwargs


def _apply_post_hooks(url, kwargs, response):
    """Apply all post-request hooks in order."""
    for hook in _post_post_hooks:
        response = hook(url, kwargs, response)
    return response


# Wrap the requests.post function
@wrapt.patch_function_wrapper(requests, "post")
def wrapped_post(wrapped, instance, args, kwargs):
    url = args[0] if args else kwargs.get("url")
    if url is None:
        return wrapped(*args, **kwargs)

    # Apply pre-hooks
    if args:
        new_url, kwargs = _apply_pre_hooks(url, kwargs)
        args = (new_url,) + args[1:]
    else:
        new_url, kwargs = _apply_pre_hooks(url, kwargs)
        kwargs["url"] = new_url

    # Call the original function
    response = wrapped(*args, **kwargs)

    # Apply post-hooks
    response = _apply_post_hooks(url, kwargs, response)

    return response
