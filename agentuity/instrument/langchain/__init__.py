def instrument():
    """Instrument the Langchain library to work with Agentuity."""
    import importlib.util
    import logging

    logger = logging.getLogger(__name__)

    if importlib.util.find_spec("langchain_community") is None:
        logger.error(
            "Could not instrument Langchain: No module named 'langchain_community'"
        )
        return False

    if importlib.util.find_spec("langchain_core") is None:
        logger.error("Could not instrument Langchain: No module named 'langchain_core'")
        return False

    try:
        from langchain_core.callbacks import BaseCallbackHandler
        from opentelemetry import trace

        class AgentuityCallbackHandler(BaseCallbackHandler):
            """Callback handler that reports Langchain operations to OpenTelemetry."""

            def __init__(self):
                self.tracer = trace.get_tracer(__name__)
                self.spans = {}

            def on_chain_start(self, serialized, inputs, **kwargs):
                """Start a span when a chain starts."""
                span = self.tracer.start_span(
                    name=f"langchain.chain.{serialized.get('name', 'unknown')}",
                    attributes={
                        "@agentuity/provider": "langchain",
                        "chain_type": serialized.get("name", "unknown"),
                    },
                )
                self.spans[id(serialized)] = span

            def on_chain_end(self, outputs, **kwargs):
                """End the span when a chain completes."""
                span_id = id(kwargs.get("serialized", {}))
                if span_id in self.spans:
                    span = self.spans.pop(span_id)
                    span.set_status(trace.StatusCode.OK)
                    span.end()

        from langchain_core.callbacks import set_handler

        set_handler(AgentuityCallbackHandler())

        logger.info("Configured Langchain to work with Agentuity")
        return True
    except ImportError as e:
        logger.error(f"Error instrumenting Langchain: {str(e)}")
        return False
