def patch_span():
    import functools
    from opentelemetry.sdk.trace import Span

    # Save the original set_attribute method
    original_set_attribute = Span.set_attribute

    @functools.wraps(original_set_attribute)
    def safe_set_attribute(self, key, value):
        try:
            # If value is already a valid type, use it
            if isinstance(value, (bool, str, bytes, int, float)):
                return original_set_attribute(self, key, value)

            # If value is a list/tuple, ensure all elements are valid
            if isinstance(value, (list, tuple)) and all(
                isinstance(v, (bool, str, bytes, int, float)) for v in value
            ):
                return original_set_attribute(self, key, value)

            # Convert unsupported values (e.g., NotGiven, dicts) to strings
            return original_set_attribute(self, key, str(value))

        except Exception as e:
            print(f"Skipping invalid attribute {key}: {value} ({e})")

    # Apply the patch to the concrete SDK implementation of Span
    Span.set_attribute = safe_set_attribute
