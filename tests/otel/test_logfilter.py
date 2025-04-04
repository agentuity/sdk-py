import logging
import sys
from unittest.mock import MagicMock

sys.modules['openlit'] = MagicMock()

from agentuity.otel.logfilter import ModuleFilter, exclude_signatures  # noqa: E402


class TestModuleFilter:
    """Test suite for the ModuleFilter class."""
    
    def test_init(self):
        """Test initialization of ModuleFilter."""
        filter = ModuleFilter()
        assert isinstance(filter, logging.Filter)
        
    def test_filter_excluded_module(self):
        """Test filtering of excluded modules."""
        filter = ModuleFilter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "connectionpool"
        record.funcName = "_make_request"
        
        assert filter.filter(record) is False
        
    def test_filter_non_excluded_module(self):
        """Test filtering of non-excluded modules."""
        filter = ModuleFilter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        assert filter.filter(record) is True
        
    def test_exclude_signatures_content(self):
        """Test that exclude_signatures contains expected values."""
        assert "connectionpool._make_request" in exclude_signatures
        assert "connectionpool._new_conn" in exclude_signatures
