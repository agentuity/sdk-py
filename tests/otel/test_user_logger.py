import logging
from unittest.mock import MagicMock, patch
from agentuity.otel.logger import (
    add_user_logger_provider, 
    emit_to_user_providers,
    MultiDelegateHandler,
    create_logger,
    _user_logger_providers
)


class TestUserLoggerProvider:
    """Test user logger provider multi-delegate functionality."""

    def setup_method(self):
        """Clear user logger providers before each test."""
        _user_logger_providers.clear()

    def teardown_method(self):
        """Clear user logger providers after each test."""
        _user_logger_providers.clear()

    def test_add_user_logger_provider(self):
        """Test adding a user logger provider."""
        mock_provider = MagicMock()
        
        assert len(_user_logger_providers) == 0
        
        add_user_logger_provider(mock_provider)
        
        assert len(_user_logger_providers) == 1
        assert _user_logger_providers[0] == mock_provider

    def test_add_multiple_user_logger_providers(self):
        """Test adding multiple user logger providers."""
        mock_provider1 = MagicMock()
        mock_provider2 = MagicMock()
        
        add_user_logger_provider(mock_provider1)
        add_user_logger_provider(mock_provider2)
        
        assert len(_user_logger_providers) == 2
        assert mock_provider1 in _user_logger_providers
        assert mock_provider2 in _user_logger_providers

    def test_emit_to_user_providers_no_providers(self):
        """Test emitting when no user providers are registered."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Should not raise any errors
        emit_to_user_providers(record)

    @patch('agentuity.otel.logger.logging.warning')
    def test_emit_to_user_providers_success(self, mock_warning):
        """Test successful emission to user providers."""
        mock_otel_logger = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_logger.return_value = mock_otel_logger
        
        add_user_logger_provider(mock_provider)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test"
        record.funcName = "test_function"
        
        # Just test that the function runs without error and calls the provider
        emit_to_user_providers(record)
        
        # Verify provider was called
        mock_provider.get_logger.assert_called_once()
        
        # Verify otel logger emit was called
        mock_otel_logger.emit.assert_called_once()
        
        # Should not log warning for successful emission
        mock_warning.assert_not_called()

    @patch('agentuity.otel.logger.logging.warning')
    def test_emit_to_user_providers_error_handling(self, mock_warning):
        """Test error handling when provider emission fails."""
        mock_provider = MagicMock()
        mock_provider.get_logger.side_effect = Exception("Provider error")
        
        add_user_logger_provider(mock_provider)
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test error message",
            args=(),
            exc_info=None
        )
        
        # Should not raise the exception
        emit_to_user_providers(record)
        
        # Should log warning
        mock_warning.assert_called_once()
        assert "Error emitting to user logger provider" in str(mock_warning.call_args)

    def test_emit_to_user_providers_severity_mapping(self):
        """Test correct severity level mapping."""
        from opentelemetry._logs import SeverityNumber
        
        mock_otel_logger = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_logger.return_value = mock_otel_logger
        
        add_user_logger_provider(mock_provider)
        
        # Expected severity mapping
        severity_mapping = {
            logging.DEBUG: SeverityNumber.DEBUG,
            logging.INFO: SeverityNumber.INFO,
            logging.WARNING: SeverityNumber.WARN,
            logging.ERROR: SeverityNumber.ERROR,
            logging.CRITICAL: SeverityNumber.FATAL,
        }
        
        for log_level, expected_severity in severity_mapping.items():
            # Reset mock calls for clean test
            mock_otel_logger.reset_mock()
            mock_provider.reset_mock()
            
            record = logging.LogRecord(
                name="test",
                level=log_level,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            # Call emit_to_user_providers
            emit_to_user_providers(record)
            
            # Verify provider.get_logger was called
            mock_provider.get_logger.assert_called_once()
            
            # Verify mock_otel_logger.emit was called with correct severity
            mock_otel_logger.emit.assert_called_once()
            call_args = mock_otel_logger.emit.call_args
            
            # Check that severity_number matches expected mapping
            assert call_args.kwargs['severity_number'] == expected_severity
            assert call_args.kwargs['body'] == "Test message"

    def test_emit_to_user_providers_custom_attributes(self):
        """Test that custom attributes from log record are included and private attributes are filtered."""
        mock_otel_logger = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_logger.return_value = mock_otel_logger
        
        add_user_logger_provider(mock_provider)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Add custom attributes
        record.custom_attr = "custom_value"
        record.user_id = "12345"
        record._private_attr = "should_be_ignored"  # Should be filtered out
        
        # Should not raise errors when processing custom attributes
        emit_to_user_providers(record)
        
        # Verify provider was called
        mock_provider.get_logger.assert_called()
        mock_otel_logger.emit.assert_called()
        
        # Verify the attributes passed to emit
        call_args = mock_otel_logger.emit.call_args
        emitted_attributes = call_args.kwargs['attributes']
        
        # Assert custom attributes are included
        assert 'custom_attr' in emitted_attributes
        assert emitted_attributes['custom_attr'] == "custom_value"
        assert 'user_id' in emitted_attributes
        assert emitted_attributes['user_id'] == "12345"
        
        # Assert private attributes are filtered out
        assert '_private_attr' not in emitted_attributes


class TestMultiDelegateHandler:
    """Test the MultiDelegateHandler logging handler."""

    def setup_method(self):
        """Clear user logger providers before each test."""
        _user_logger_providers.clear()

    def teardown_method(self):
        """Clear user logger providers after each test."""
        _user_logger_providers.clear()

    def test_multi_delegate_handler_emit(self):
        """Test that MultiDelegateHandler correctly calls emit_to_user_providers when providers exist."""
        # Add a mock provider so handler doesn't no-op
        mock_provider = MagicMock()
        add_user_logger_provider(mock_provider)
        
        handler = MultiDelegateHandler()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        with patch('agentuity.otel.logger.emit_to_user_providers') as mock_emit:
            handler.emit(record)
            mock_emit.assert_called_once_with(record)

    def test_multi_delegate_handler_emit_no_providers(self):
        """Test that MultiDelegateHandler no-ops when no providers are registered."""
        handler = MultiDelegateHandler()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        with patch('agentuity.otel.logger.emit_to_user_providers') as mock_emit:
            handler.emit(record)
            mock_emit.assert_not_called()  # Should not be called when no providers


class TestCreateLoggerWithMultiDelegate:
    """Test the enhanced create_logger function with multi-delegate support."""

    def setup_method(self):
        """Clear user logger providers before each test.""" 
        _user_logger_providers.clear()

    def teardown_method(self):
        """Clear user logger providers after each test."""
        _user_logger_providers.clear()

    def test_create_logger_no_user_providers(self):
        """Test create_logger without user providers still adds handler for later use."""
        parent_logger = logging.getLogger("test_parent")
        
        child = create_logger(parent_logger, "child", {"attr1": "value1"})
        
        assert child.name == "test_parent.child"
        assert len(child.handlers) == 1  # Multi-delegate handler always added now
        assert isinstance(child.handlers[0], MultiDelegateHandler)

    def test_create_logger_with_user_providers(self):
        """Test create_logger with user providers adds multi-delegate handler."""
        mock_provider = MagicMock()
        add_user_logger_provider(mock_provider)
        
        parent_logger = logging.getLogger("test_parent")
        
        child = create_logger(parent_logger, "child", {"attr1": "value1"})
        
        assert child.name == "test_parent.child"
        
        # Should have added a MultiDelegateHandler
        multi_handlers = [h for h in child.handlers if isinstance(h, MultiDelegateHandler)]
        assert len(multi_handlers) == 1
        assert multi_handlers[0].level == logging.DEBUG

    def test_create_logger_prevents_duplicate_handler(self):
        """Test that create_logger doesn't add duplicate MultiDelegateHandler when called multiple times."""
        mock_provider = MagicMock()
        add_user_logger_provider(mock_provider)
        
        parent_logger = logging.getLogger("test_parent")
        
        # Create logger first time
        child1 = create_logger(parent_logger, "child", {"attr1": "value1"})
        
        # Should have exactly one MultiDelegateHandler
        multi_handlers_first = [h for h in child1.handlers if isinstance(h, MultiDelegateHandler)]
        assert len(multi_handlers_first) == 1
        
        # Get the actual child logger that was created (using Python's logger hierarchy)
        actual_child = parent_logger.getChild("child")
        
        # Manually add a MultiDelegateHandler to simulate what would happen 
        # if create_logger didn't have duplicate prevention
        extra_handler = MultiDelegateHandler()
        actual_child.addHandler(extra_handler)
        
        # Now we should have 2 handlers
        multi_handlers_with_extra = [h for h in actual_child.handlers if isinstance(h, MultiDelegateHandler)]
        assert len(multi_handlers_with_extra) == 2
        
        # Call create_logger again with the same parent and name
        child2 = create_logger(parent_logger, "child", {"attr2": "value2"})
        
        # Should return the same logger instance (Python logger behavior)
        assert child2 is actual_child
        
        # The duplicate prevention logic should prevent adding another handler
        # So we should still have only 2 handlers (not 3)
        multi_handlers_final = [h for h in child2.handlers if isinstance(h, MultiDelegateHandler)]
        assert len(multi_handlers_final) == 2

    def test_create_logger_attributes_filter(self):
        """Test that create_logger adds ContextFilter for attributes."""
        parent_logger = logging.getLogger("test_parent")
        
        child = create_logger(parent_logger, "child", {"custom_attr": "test_value"})
        
        # Create a test record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Apply filters (simulating what logging does)
        for filter_obj in child.filters:
            filter_obj.filter(record)
        
        # Check that custom attribute was added
        assert hasattr(record, 'custom_attr')
        assert record.custom_attr == "test_value"

    def test_retroactive_handler_attachment(self):
        """Test that handlers are retroactively attached to existing loggers when providers are added."""
        parent_logger = logging.getLogger("test_retroactive")
        
        # Create logger (gets a handler)
        child = create_logger(parent_logger, "child", {"attr1": "value1"})
        
        # Verify it has a handler
        assert len(child.handlers) == 1
        assert isinstance(child.handlers[0], MultiDelegateHandler)
        
        # Remove handler to simulate logger in old state (before multi-delegate was added)
        child.handlers.clear()
        assert len(child.handlers) == 0
        
        # Add provider (should trigger retroactive attachment to child)
        mock_provider = MagicMock()
        add_user_logger_provider(mock_provider)
        
        # Verify handler was retroactively attached
        assert len(child.handlers) == 1
        assert isinstance(child.handlers[0], MultiDelegateHandler)

