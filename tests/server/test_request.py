import pytest
import sys
from unittest.mock import MagicMock

sys.modules["openlit"] = MagicMock()

from agentuity.server.request import AgentRequest  # noqa: E402
from agentuity.server.data import Data  # noqa: E402


class TestAgentRequest:
    """Test suite for the AgentRequest class."""

    def test_init(self):
        """Test initialization of AgentRequest."""
        req_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",  # "Hello, world!" in base64
            "metadata": {"key": "value"},
        }
        request = AgentRequest(req_data)
        assert isinstance(request, AgentRequest)
        assert isinstance(request.data, Data)
        assert request["contentType"] == "text/plain"
        assert request["trigger"] == "manual"

    def test_validate_success(self):
        """Test validation with valid request data."""
        req_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
        }
        request = AgentRequest(req_data)
        assert request.validate() is True

    def test_validate_missing_content_type(self):
        """Test validation fails when contentType is missing."""
        req_data = {
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
        }
        request = AgentRequest(req_data)
        with pytest.raises(
            ValueError, match="Request must contain 'contentType' field"
        ):
            request.validate()

    def test_validate_missing_trigger(self):
        """Test validation fails when trigger is missing."""
        req_data = {
            "contentType": "text/plain",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
        }
        request = AgentRequest(req_data)
        with pytest.raises(ValueError, match="Request requires 'trigger' field"):
            request.validate()

    def test_data_property(self):
        """Test the data property returns the Data object."""
        req_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
        }
        request = AgentRequest(req_data)
        assert isinstance(request.data, Data)

    def test_trigger_property(self):
        """Test the trigger property returns the trigger value."""
        req_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
        }
        request = AgentRequest(req_data)
        assert request.trigger == "manual"

    def test_metadata_property(self):
        """Test the metadata property returns the metadata dict."""
        req_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
            "metadata": {"key": "value"},
        }
        request = AgentRequest(req_data)
        assert request.metadata == {"key": "value"}

    def test_metadata_default(self):
        """Test metadata property returns empty dict if not present."""
        req_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
        }
        request = AgentRequest(req_data)
        assert request.metadata == {}

    def test_get_method(self):
        """Test get method retrieves value from metadata."""
        req_data = {
            "contentType": "text/plain",
            "trigger": "manual",
            "payload": "SGVsbG8sIHdvcmxkIQ==",
            "metadata": {"key": "value"},
        }
        request = AgentRequest(req_data)
        assert request.get("key") == "value"
        assert request.get("non_existent") is None
        assert request.get("non_existent", "default") == "default"
