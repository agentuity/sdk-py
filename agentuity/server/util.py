import warnings
import functools


def deprecated(reason: str):
    """
    Decorator to mark functions or properties as deprecated.
    """

    def decorator(obj):
        if isinstance(obj, property):
            # Wrap property getter, setter, deleter
            getter = obj.fget
            setter = obj.fset
            deleter = obj.fdel

            def wrap_func(func):
                @functools.wraps(func)
                def wrapped(*args, **kwargs):
                    warnings.warn(reason, DeprecationWarning, stacklevel=2)
                    return func(*args, **kwargs)

                return wrapped

            return property(
                wrap_func(getter) if getter else None,
                wrap_func(setter) if setter else None,
                wrap_func(deleter) if deleter else None,
                doc=obj.__doc__,
            )
        else:

            @functools.wraps(obj)
            def wrapper(*args, **kwargs):
                warnings.warn(reason, DeprecationWarning, stacklevel=2)
                return obj(*args, **kwargs)

            return wrapper

    return decorator
