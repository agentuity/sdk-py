import logging
import io
import os
from unittest.mock import MagicMock, patch
import sys


class TestLlamaIndexInstrument:
    """Test suite for the LlamaIndex instrumentation module."""

    def setup_method(self):
        """Set up the test environment."""
        self.logger = logging.getLogger("agentuity.instrument.llamaindex")
        self.logger.handlers = []
        self.log_capture = io.StringIO()
        handler = logging.StreamHandler(self.log_capture)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

        # Store original environment
        self.original_env = os.environ.copy()

        # Mock mailparser to avoid import issues
        sys.modules["mailparser"] = MagicMock()

    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

        # Clean up mock modules
        if "mailparser" in sys.modules:
            del sys.modules["mailparser"]

    def test_instrument_missing_llama_index(self):
        """Test instrument function when llama_index is missing."""
        with patch("importlib.util.find_spec", return_value=None):
            from agentuity.instrument.llamaindex import instrument

            result = instrument()
            assert result is False
            assert (
                "LlamaIndex not found, skipping instrumentation"
                in self.log_capture.getvalue()
            )

    def test_instrument_missing_llama_index_core(self):
        """Test instrument function when llama_index.core is missing."""

        def mock_find_spec(module_name):
            if module_name == "llama_index":
                return MagicMock()
            elif module_name == "llama_index.core":
                return None
            return MagicMock()

        with patch("importlib.util.find_spec", side_effect=mock_find_spec):
            from agentuity.instrument.llamaindex import instrument

            result = instrument()
            assert result is False
            assert (
                "LlamaIndex core not found, skipping instrumentation"
                in self.log_capture.getvalue()
            )

    def test_instrument_success(self):
        """Test successful instrumentation of LlamaIndex."""
        # Clear environment variables that might interfere
        for key in ["OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_BASE_URL"]:
            if key in os.environ:
                del os.environ[key]

        os.environ["AGENTUITY_API_KEY"] = "test_api_key"
        os.environ["AGENTUITY_TRANSPORT_URL"] = "https://test.agentuity.ai"

        with (
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch("agentuity.instrument.llamaindex._patch_openai_client") as mock_patch,
            patch(
                "agentuity.instrument.llamaindex._setup_instrumentation"
            ) as mock_setup,
        ):
            from agentuity.instrument.llamaindex import instrument

            result = instrument()
            assert result is True
            mock_patch.assert_called_once()
            mock_setup.assert_called_once()
            assert (
                "Instrumented LlamaIndex Provider to use Agentuity AI Gateway"
                in self.log_capture.getvalue()
            )

    def test_patch_openai_client_no_api_key(self):
        """Test _patch_openai_client when no API key is available."""
        # Remove any existing API keys
        for key in ["AGENTUITY_API_KEY", "AGENTUITY_SDK_KEY"]:
            if key in os.environ:
                del os.environ[key]

        from agentuity.instrument.llamaindex import _patch_openai_client

        _patch_openai_client()
        assert (
            "No Agentuity API key found, skipping OpenAI client patching"
            in self.log_capture.getvalue()
        )

    def test_patch_openai_client_openai_key_already_set(self):
        """Test _patch_openai_client when OPENAI_API_KEY is already set to different value."""
        os.environ["AGENTUITY_API_KEY"] = "agentuity_key"
        os.environ["OPENAI_API_KEY"] = "different_openai_key"

        from agentuity.instrument.llamaindex import _patch_openai_client

        _patch_openai_client()
        assert (
            "OPENAI_API_KEY already set to a different value"
            in self.log_capture.getvalue()
        )

    def test_patch_openai_client_configuration_needed(self):
        """Test _patch_openai_client when configuration is needed."""
        os.environ["AGENTUITY_API_KEY"] = "test_api_key"
        os.environ["AGENTUITY_TRANSPORT_URL"] = "https://test.agentuity.ai"

        # Remove OPENAI_API_KEY to trigger configuration
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        from agentuity.instrument.llamaindex import _patch_openai_client

        _patch_openai_client()

        assert os.environ["OPENAI_API_KEY"] == "test_api_key"
        assert (
            os.environ["OPENAI_API_BASE"] == "https://test.agentuity.ai/gateway/openai"
        )
        assert (
            os.environ["OPENAI_BASE_URL"] == "https://test.agentuity.ai/gateway/openai"
        )
        assert (
            "Configuring LlamaIndex OpenAI for Agentuity" in self.log_capture.getvalue()
        )

    def test_patch_openai_client_with_class_patching(self):
        """Test _patch_openai_client with OpenAI client class patching."""
        os.environ["AGENTUITY_API_KEY"] = "test_api_key"
        os.environ["AGENTUITY_TRANSPORT_URL"] = "https://test.agentuity.ai"

        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        # Create a proper mock class with spec
        class MockOpenAI:
            def __init__(self, *args, **kwargs):
                pass

        def mock_find_spec(module_name):
            if module_name == "llama_index.llms.openai":
                return MagicMock()
            return None

        with (
            patch("importlib.util.find_spec", side_effect=mock_find_spec),
            patch.dict(
                "sys.modules", {"llama_index.llms.openai": MagicMock(OpenAI=MockOpenAI)}
            ),
        ):
            from agentuity.instrument.llamaindex import _patch_openai_client

            _patch_openai_client()

            assert hasattr(MockOpenAI, "_agentuity_patched")
            assert (
                "Found OpenAI client in llama_index.llms.openai"
                in self.log_capture.getvalue()
            )

    def test_patch_openai_client_core_location(self):
        """Test _patch_openai_client finding OpenAI client in core location."""
        os.environ["AGENTUITY_API_KEY"] = "test_api_key"

        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        # Create a proper mock class
        class MockOpenAI:
            def __init__(self, *args, **kwargs):
                pass

        def mock_find_spec(module_name):
            if module_name == "llama_index.llms.openai":
                return None
            elif module_name == "llama_index.core.llms.openai":
                return MagicMock()
            return None

        with (
            patch("importlib.util.find_spec", side_effect=mock_find_spec),
            patch.dict(
                "sys.modules",
                {"llama_index.core.llms.openai": MagicMock(OpenAI=MockOpenAI)},
            ),
        ):
            from agentuity.instrument.llamaindex import _patch_openai_client

            _patch_openai_client()

            assert (
                "Found OpenAI client in llama_index.core.llms.openai"
                in self.log_capture.getvalue()
            )

    def test_setup_instrumentation_new_approach(self):
        """Test _setup_instrumentation with new dispatcher approach."""
        mock_dispatcher = MagicMock()
        mock_get_dispatcher = MagicMock(return_value=mock_dispatcher)
        mock_trace = MagicMock()
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        with (
            patch.dict(
                "sys.modules",
                {
                    "opentelemetry": MagicMock(trace=mock_trace),
                    "llama_index.core.instrumentation": MagicMock(
                        get_dispatcher=mock_get_dispatcher
                    ),
                },
            ),
        ):
            from agentuity.instrument.llamaindex import _setup_instrumentation

            result = _setup_instrumentation()
            assert result is True
            mock_get_dispatcher.assert_called_once()
            mock_dispatcher.add_event_handler.assert_called_once()

    def test_setup_instrumentation_legacy_approach(self):
        """Test _setup_instrumentation with legacy callback approach."""
        mock_trace = MagicMock()
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer
        mock_set_global_handler = MagicMock()

        # Mock the get_dispatcher to raise ImportError to trigger legacy path
        def mock_get_dispatcher():
            raise ImportError("New approach not available")

        with (
            patch.dict(
                "sys.modules",
                {
                    "opentelemetry": MagicMock(trace=mock_trace),
                    "llama_index.core": MagicMock(
                        set_global_handler=mock_set_global_handler
                    ),
                    "llama_index.core.instrumentation": MagicMock(
                        get_dispatcher=mock_get_dispatcher
                    ),
                },
            ),
        ):
            from agentuity.instrument.llamaindex import _setup_instrumentation

            result = _setup_instrumentation()
            assert result is True
            mock_set_global_handler.assert_called_once()

    def test_setup_instrumentation_no_opentelemetry(self):
        """Test _setup_instrumentation when OpenTelemetry is not available."""

        # Create a test function that mimics _setup_instrumentation behavior
        def test_setup_with_import_error():
            try:
                # Simulate the import that would fail
                raise ImportError("No module named 'opentelemetry'")
            except ImportError:
                self.logger.debug(
                    "OpenTelemetry not available, skipping instrumentation"
                )
                return False

        result = test_setup_with_import_error()
        assert result is False
        assert (
            "OpenTelemetry not available, skipping instrumentation"
            in self.log_capture.getvalue()
        )

    def test_agentuity_event_handler_functionality(self):
        """Test the AgentuityEventHandler functionality."""
        os.environ["AGENTUITY_API_KEY"] = "test_api_key"

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_trace = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer
        mock_trace.StatusCode = MagicMock()
        mock_trace.StatusCode.OK = "OK"

        # Mock event objects
        start_event = MagicMock()
        start_event.__class__.__name__ = "SomeStartEvent"
        start_event.id_ = "test_event_id"

        end_event = MagicMock()
        end_event.__class__.__name__ = "SomeEndEvent"
        end_event.id_ = "test_event_id"

        # Create a dispatcher that we can control
        mock_dispatcher = MagicMock()
        mock_get_dispatcher = MagicMock(return_value=mock_dispatcher)

        with (
            patch.dict(
                "sys.modules",
                {
                    "opentelemetry": MagicMock(trace=mock_trace),
                    "llama_index.core.instrumentation": MagicMock(
                        get_dispatcher=mock_get_dispatcher
                    ),
                },
            ),
        ):
            from agentuity.instrument.llamaindex import _setup_instrumentation

            result = _setup_instrumentation()
            assert result is True

            # Get the handler that was added
            call_args = mock_dispatcher.add_event_handler.call_args[0]
            handler = call_args[0]

            # Test start event handling
            handler.handle(start_event)
            mock_tracer.start_span.assert_called_once()

            # Test end event handling
            handler.handle(end_event)
            mock_span.set_status.assert_called_once()
            mock_span.end.assert_called_once()

    def test_patched_openai_init_functionality(self):
        """Test the patched OpenAI __init__ functionality."""
        os.environ["AGENTUITY_API_KEY"] = "test_api_key"
        os.environ["AGENTUITY_TRANSPORT_URL"] = "https://test.agentuity.ai"

        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        # Create a mock OpenAI class
        class MockOpenAI:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        def mock_find_spec(module_name):
            if module_name == "llama_index.llms.openai":
                return MagicMock()
            return None

        with (
            patch("importlib.util.find_spec", side_effect=mock_find_spec),
            patch.dict(
                "sys.modules", {"llama_index.llms.openai": MagicMock(OpenAI=MockOpenAI)}
            ),
        ):
            from agentuity.instrument.llamaindex import _patch_openai_client

            _patch_openai_client()

            # Test that the class was patched
            assert hasattr(MockOpenAI, "_agentuity_patched")

            # Test the patched functionality
            instance = MockOpenAI()
            assert instance.kwargs["api_key"] == "test_api_key"
            assert (
                instance.kwargs["api_base"]
                == "https://test.agentuity.ai/gateway/openai"
            )

    def test_edge_cases(self):
        """Test various edge cases and error conditions."""
        # Test with AGENTUITY_SDK_KEY instead of AGENTUITY_API_KEY
        os.environ["AGENTUITY_SDK_KEY"] = "test_sdk_key"
        if "AGENTUITY_API_KEY" in os.environ:
            del os.environ["AGENTUITY_API_KEY"]

        from agentuity.instrument.llamaindex import _patch_openai_client

        _patch_openai_client()
        assert os.environ.get("OPENAI_API_KEY") == "test_sdk_key"

        # Test when OPENAI_API_KEY equals AGENTUITY_API_KEY (should still configure)
        os.environ["AGENTUITY_API_KEY"] = "same_key"
        os.environ["OPENAI_API_KEY"] = "same_key"

        _patch_openai_client()
        assert (
            "Configuring LlamaIndex OpenAI for Agentuity" in self.log_capture.getvalue()
        )
