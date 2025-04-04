import pytest
import logging
import sys
from unittest.mock import MagicMock

sys.modules['openlit'] = MagicMock()

from agentuity.otel.logger import create_logger  # noqa: E402


class TestLogger:
    """Test suite for the logger module."""
    
    @pytest.fixture
    def mock_parent_logger(self):
        """Create a mock parent logger for testing."""
        logger = MagicMock(spec=logging.Logger)
        child_logger = MagicMock(spec=logging.Logger)
        logger.getChild.return_value = child_logger
        return logger, child_logger
    
    def test_create_logger(self, mock_parent_logger):
        """Test creating a child logger with attributes."""
        parent_logger, child_logger = mock_parent_logger
        attributes = {"key1": "value1", "key2": "value2"}
        
        result = create_logger(parent_logger, "test_name", attributes)
        
        assert result == child_logger
        parent_logger.getChild.assert_called_once_with("test_name")
        child_logger.addFilter.assert_called_once()
        
        filter_instance = child_logger.addFilter.call_args[0][0]
        assert isinstance(filter_instance, logging.Filter)
    
    def test_context_filter(self, mock_parent_logger):
        """Test the ContextFilter class."""
        parent_logger, child_logger = mock_parent_logger
        attributes = {"key1": "value1", "key2": "value2"}
        
        create_logger(parent_logger, "test_name", attributes)
        
        filter_instance = child_logger.addFilter.call_args[0][0]
        
        record = MagicMock(spec=logging.LogRecord)
        filter_instance.filter(record)
        
        assert record.key1 == "value1"
        assert record.key2 == "value2"
    
    def test_create_logger_with_empty_attributes(self, mock_parent_logger):
        """Test creating a logger with empty attributes."""
        parent_logger, child_logger = mock_parent_logger
        attributes = {}
        
        result = create_logger(parent_logger, "test_name", attributes)
        
        assert result == child_logger
        parent_logger.getChild.assert_called_once_with("test_name")
        child_logger.addFilter.assert_called_once()
        
        filter_instance = child_logger.addFilter.call_args[0][0]
        
        record = MagicMock(spec=logging.LogRecord)
        filter_instance.filter(record)
        
        assert not hasattr(record, "key1")
    
    def test_create_logger_integration(self):
        """Test create_logger with actual logging objects."""
        logger = logging.getLogger("test_parent")
        
        records = []
        
        class CapturingHandler(logging.Handler):
            def emit(self, record):
                records.append(record)
        
        handler = CapturingHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        attributes = {"agent_id": "test_agent", "request_id": "123456"}
        child_logger = create_logger(logger, "child", attributes)
        
        child_logger.info("Test message")
        
        assert len(records) == 1
        record = records[0]
        assert record.agent_id == "test_agent"
        assert record.request_id == "123456"
        assert record.name == "test_parent.child"
        assert record.getMessage() == "Test message"
