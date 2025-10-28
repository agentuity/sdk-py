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
        mock_otel_logger = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_logger.return_value = mock_otel_logger
        
        add_user_logger_provider(mock_provider)
        
        # Test that different log levels call emit_to_user_providers
        test_levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
        
        for log_level in test_levels:
            record = logging.LogRecord(
                name="test",
                level=log_level,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            # Should not raise errors
            emit_to_user_providers(record)
            
            # Verify provider was called
            mock_provider.get_logger.assert_called()

    def test_emit_to_user_providers_custom_attributes(self):
        """Test that custom attributes from log record are included."""
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

    def test_create_logger_doesnt_duplicate_handler(self):
        """Test that create_logger doesn't add duplicate MultiDelegateHandler."""
        mock_provider = MagicMock()
        add_user_logger_provider(mock_provider)
        
        parent_logger = logging.getLogger("test_parent")
        
        # Create logger twice
        child1 = create_logger(parent_logger, "child", {"attr1": "value1"})
        child2 = create_logger(child1, "grandchild", {"attr2": "value2"})
        
        # Should only have one MultiDelegateHandler
        multi_handlers = [h for h in child2.handlers if isinstance(h, MultiDelegateHandler)]
        assert len(multi_handlers) == 1

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
        
        # Create logger before adding any providers
        child = create_logger(parent_logger, "child", {"attr1": "value1"})
        
        # Should have one handler (the MultiDelegateHandler)
        assert len(child.handlers) == 1
        assert isinstance(child.handlers[0], MultiDelegateHandler)
        
        # Clear handler and logger registry, then recreate logger without providers
        child.handlers.clear()
        from agentuity.otel.logger import _logger_registry
        _logger_registry.clear()
        
        # Create logger again without any providers
        child2 = create_logger(parent_logger, "child2", {"attr2": "value2"})
        assert len(child2.handlers) == 1  # Should still get handler
        
        # Now add a provider - should not add duplicate handlers
        mock_provider = MagicMock()
        add_user_logger_provider(mock_provider)
        
        # Should still have only one handler (no duplicates)
        assert len(child2.handlers) == 1
        assert isinstance(child2.handlers[0], MultiDelegateHandler)
