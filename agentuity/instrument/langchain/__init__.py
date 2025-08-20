def instrument():
    """Instrument the Langchain library to work with Agentuity."""
    import importlib.util
    import logging

    logger = logging.getLogger(__name__)

    # Check if already instrumented by looking for our callback handler
    try:
        from langchain_core.callbacks import BaseCallbackHandler

        if hasattr(BaseCallbackHandler, "_agentuity_handler_registered"):
            logger.debug("Langchain already instrumented")
            return True
    except ImportError:
        pass

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
        import langchain_core

        class AgentuityCallbackHandler(BaseCallbackHandler):
            """Callback handler that reports Langchain operations to OpenTelemetry."""

            def __init__(self):
                self.tracer = trace.get_tracer(__name__)
                self.spans = {}

            def on_chain_start(self, serialized, inputs, **kwargs):
                """Start a span when a chain starts."""
                try:
                    # Use start_as_current_span for proper context propagation.
                    # We must manually enter and later exit the context manager
                    # to ensure attach/detach happens in the same coroutine.
                    cm = self.tracer.start_as_current_span(
                        name=f"langchain.chain.{serialized.get('name', 'unknown')}",
                        attributes={
                            "@agentuity/provider": "langchain",
                            "chain_type": serialized.get("name", "unknown"),
                            "langchain.inputs": str(inputs)[:500] if inputs else "",
                        },
                    )
                    span = cm.__enter__()
                    # Store both span and context manager for proper cleanup later
                    self.spans[id(serialized)] = (span, cm)
                except Exception:
                    # If span creation fails, don't break the chain execution
                    pass

            def on_chain_end(self, outputs, **kwargs):
                """End the span when a chain completes."""
                try:
                    span_id = id(kwargs.get("serialized", {}))
                    if span_id in self.spans:
                        stored = self.spans.pop(span_id)
                        # Support both legacy storage (span) and new (span, cm)
                        if isinstance(stored, tuple):
                            span, cm = stored
                        else:
                            span, cm = stored, None

                        # Add output information
                        if outputs:
                            span.set_attribute("langchain.outputs", str(outputs)[:500])
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        # Properly detach context and end span via context manager
                        if cm is not None:
                            cm.__exit__(None, None, None)
                        else:
                            span.end()
                except Exception:
                    # If span cleanup fails, don't break the chain execution
                    pass

            def on_chain_error(self, error, **kwargs):
                """Handle span when a chain errors."""
                try:
                    span_id = id(kwargs.get("serialized", {}))
                    if span_id in self.spans:
                        stored = self.spans.pop(span_id)
                        # Support both legacy storage (span) and new (span, cm)
                        if isinstance(stored, tuple):
                            span, cm = stored
                        else:
                            span, cm = stored, None

                        # Record the error
                        span.record_exception(error)
                        span.set_status(
                            trace.Status(trace.StatusCode.ERROR, str(error))
                        )
                        # Properly detach context and end span via context manager
                        if cm is not None:
                            tb = getattr(error, "__traceback__", None)
                            cm.__exit__(type(error), error, tb)
                        else:
                            span.end()
                    else:
                        # Create a standalone error span if we don't have the original
                        span = self.tracer.start_span(
                            name="langchain.chain.error",
                            attributes={
                                "@agentuity/provider": "langchain",
                                "error.type": type(error).__name__,
                                "error.message": str(error),
                            },
                        )
                        span.record_exception(error)
                        span.set_status(
                            trace.Status(trace.StatusCode.ERROR, str(error))
                        )
                        span.end()
                except Exception:
                    # If span cleanup fails, don't break the chain execution
                    pass

        # Mark as instrumented and register the handler
        BaseCallbackHandler._agentuity_handler_registered = True

        # Register the callback handler using LangChain's context vars
        handler = AgentuityCallbackHandler()

        # Try to register with the callback manager
        if hasattr(langchain_core.callbacks, "manager"):
            try:
                # Set the handler in the tracing context
                langchain_core.callbacks.manager.tracing_callback_var.set([handler])
            except AttributeError:
                # Fallback: Try setting it as a default callback
                if hasattr(langchain_core.callbacks.manager, "CallbackManager"):
                    import os

                    os.environ.setdefault("LANGCHAIN_CALLBACKS", str([handler]))
                    logger.debug("Set callback handler via environment variable")
        logger.info("Configured Langchain to work with Agentuity")
        return True
    except ImportError as e:
        logger.error(f"Error instrumenting Langchain: {str(e)}")
        return False
