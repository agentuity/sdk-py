import pytest
from unittest.mock import MagicMock
from opentelemetry import trace


@pytest.fixture
def mock_tracer():
    """Create a mock tracer for testing."""
    return MagicMock(spec=trace.Tracer)


@pytest.fixture
def base64_hello_world():
    """Return base64 encoded 'Hello, world!'"""
    return "SGVsbG8sIHdvcmxkIQ=="
