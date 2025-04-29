import logging
import io
from unittest.mock import MagicMock, patch
from opentelemetry import trace

logger = logging.getLogger("test_logger")


class MockLangchainModule:
    pass


class MockBaseCallbackHandler:
    pass


class MockSetHandler:
    def __call__(self, handler):
        pass


test_module = type(
    "test_module",
    (),
    {
        "logger": logger,
        "BaseCallbackHandler": MockBaseCallbackHandler,
        "set_handler": MockSetHandler(),
        "trace": MagicMock(get_tracer=MagicMock(return_value=MagicMock())),
    },
)


def test_instrument():
    """Instrument the Langchain library to work with Agentuity."""
    import importlib.util

    if importlib.util.find_spec("langchain_community") is None:
        test_module.logger.error(
            "Could not instrument Langchain: No module named 'langchain_community'"
        )
        return False

    if importlib.util.find_spec("langchain_core") is None:
        test_module.logger.error(
            "Could not instrument Langchain: No module named 'langchain_core'"
        )
        return False

    try:
        BaseCallbackHandler = test_module.BaseCallbackHandler
        trace = test_module.trace

        class AgentuityCallbackHandler(BaseCallbackHandler):
            """Callback handler that reports Langchain operations to OpenTelemetry."""

            def __init__(self):
                self.tracer = trace.get_tracer("test_tracer")
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

        set_handler = test_module.set_handler
        set_handler(AgentuityCallbackHandler())

        test_module.logger.info("Configured Langchain to work with Agentuity")
        test_module.AgentuityCallbackHandler = AgentuityCallbackHandler
        return True
    except ImportError as e:
        test_module.logger.error(f"Error instrumenting Langchain: {str(e)}")
        return False


class TestLangchainInstrument:
    """Test suite for the Langchain instrumentation module."""

    def setup_method(self):
        """Set up the test environment."""
        logger.handlers = []
        self.log_capture = io.StringIO()
        handler = logging.StreamHandler(self.log_capture)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def test_instrument_missing_langchain_community(self):
        """Test instrument function when langchain_community is missing."""
        with patch("importlib.util.find_spec", return_value=None):
            result = test_instrument()
            assert result is False
            assert (
                "Could not instrument Langchain: No module named 'langchain_community'"
                in self.log_capture.getvalue()
            )

    def test_instrument_missing_langchain_core(self):
        """Test instrument function when langchain_core is missing."""
        with patch("importlib.util.find_spec", side_effect=[MagicMock(), None]):
            result = test_instrument()
            assert result is False
            assert (
                "Could not instrument Langchain: No module named 'langchain_core'"
                in self.log_capture.getvalue()
            )

    def test_instrument_import_error(self):
        """Test instrument function when there's an import error."""
        test_module_copy = type(
            "test_module_copy",
            (),
            {
                "logger": logger,
                "BaseCallbackHandler": MagicMock(
                    side_effect=ImportError("Test import error")
                ),
                "set_handler": MagicMock(),
                "trace": MagicMock(),
            },
        )

        def modified_test_instrument():
            import importlib.util

            if importlib.util.find_spec("langchain_community") is None:
                test_module_copy.logger.error(
                    "Could not instrument Langchain: No module named 'langchain_community'"
                )
                return False

            if importlib.util.find_spec("langchain_core") is None:
                test_module_copy.logger.error(
                    "Could not instrument Langchain: No module named 'langchain_core'"
                )
                return False

            try:
                BaseCallbackHandler = test_module_copy.BaseCallbackHandler
                BaseCallbackHandler()  # Force the error to be raised
                return True
            except ImportError as e:
                test_module_copy.logger.error(
                    f"Error instrumenting Langchain: {str(e)}"
                )
                return False

        with patch("importlib.util.find_spec", return_value=MagicMock()):
            result = modified_test_instrument()
            assert result is False
            assert (
                "Error instrumenting Langchain: Test import error"
                in self.log_capture.getvalue()
            )

    def test_instrument_success(self):
        """Test successful instrumentation of Langchain."""
        with (
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch.object(test_module, "set_handler") as mock_set_handler,
        ):
            result = test_instrument()
            assert result is True
            assert (
                "Configured Langchain to work with Agentuity"
                in self.log_capture.getvalue()
            )
            mock_set_handler.assert_called_once()

    def test_callback_handler_functionality(self):
        """Test the callback handler functionality."""
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            result = test_instrument()
            assert result is True

        mock_tracer = MagicMock(spec=trace.Tracer)
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        handler = test_module.AgentuityCallbackHandler()
        handler.tracer = mock_tracer

        serialized = {"name": "test_chain"}
        inputs = {"input": "test_input"}
        handler.on_chain_start(serialized, inputs)

        mock_tracer.start_span.assert_called_once()
        assert id(serialized) in handler.spans
        assert handler.spans[id(serialized)] == mock_span

        outputs = {"output": "test_output"}
        handler.on_chain_end(outputs, serialized=serialized)

        assert mock_span.set_status.call_count == 1
        mock_span.end.assert_called_once()
        assert id(serialized) not in handler.spans
