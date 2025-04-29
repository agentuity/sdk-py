import pytest
import sys
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp.web import Request, Application, Response
from opentelemetry import trace

sys.modules["openlit"] = MagicMock()

from agentuity.server import (  # noqa: E402
    handle_agent_request,
    handle_health_check,
    handle_index,
    inject_trace_context,
)
from agentuity.server.response import AgentResponse  # noqa: E402


class TestRequestHandlers:
    """Test suite for server request handlers."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock application with agents_by_id."""
        app = MagicMock(spec=Application)
        app.__getitem__.return_value = {
            "test_agent": {
                "id": "test_agent",
                "name": "Test Agent",
                "run": AsyncMock(return_value="Test response"),
            }
        }
        return app

    @pytest.fixture
    def mock_request(self, mock_app):
        """Create a mock request object."""
        request = MagicMock(spec=Request)
        request.app = mock_app
        request.match_info = {"agent_id": "test_agent"}
        request.headers = {"Content-Type": "application/json"}
        request.json = AsyncMock(return_value={"message": "Hello, world!"})
        request.host = "localhost"
        request.path = "/test_agent"
        request.url = "http://localhost/test_agent"
        return request

    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer."""
        tracer = MagicMock(spec=trace.Tracer)
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span
        return tracer

    @pytest.mark.asyncio
    async def test_handle_health_check(self):
        """Test health check endpoint."""
        request = MagicMock()

        mock_response = MagicMock(spec=Response)
        mock_response.status = 200
        mock_response.content_type = "application/json"

        with patch("agentuity.server.web.json_response", return_value=mock_response):
            response = await handle_health_check(request)

            assert response.status == 200
            assert response.content_type == "application/json"

    @pytest.mark.asyncio
    async def test_handle_index(self, mock_request):
        """Test index endpoint."""
        mock_response = MagicMock(spec=Response)
        mock_response.status = 200
        mock_response.content_type = "text/plain"

        with patch("agentuity.server.web.Response", return_value=mock_response):
            response = await handle_index(mock_request)

            assert response.status == 200
            assert response.content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_handle_agent_request_success(self, mock_request):
        """Test successful agent request handling."""
        mock_response = MagicMock(spec=Response)
        mock_response.status = 200
        mock_response.content_type = "application/json"

        with (
            patch(
                "agentuity.server.trace.get_tracer", return_value=MagicMock()
            ) as mock_get_tracer,
            patch("agentuity.server.extract", return_value={}),
            patch(
                "agentuity.server.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
            patch("agentuity.server.web.json_response", return_value=mock_response),
        ):
            agent_response = MagicMock(spec=AgentResponse)
            agent_response.content_type = "text/plain"
            agent_response.payload = base64.b64encode(b"Test response").decode("utf-8")
            agent_response.metadata = {"key": "value"}
            agent_response.is_stream = False
            mock_run_agent.return_value = agent_response

            response = await handle_agent_request(mock_request)

            assert response.status == 200
            assert response.content_type == "application/json"

            mock_get_tracer.assert_called_once_with("http-server")

    @pytest.mark.asyncio
    async def test_handle_agent_request_agent_not_found(self, mock_request):
        """Test agent request handling when agent is not found."""
        mock_request.match_info = {"agent_id": "non_existent_agent"}

        mock_response = MagicMock(spec=Response)
        mock_response.status = 404
        mock_response.content_type = "text/plain"

        with patch("agentuity.server.web.Response", return_value=mock_response):
            response = await handle_agent_request(mock_request)

            assert response.status == 404
            assert response.content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_handle_agent_request_invalid_json(self, mock_request):
        """Test agent request handling with invalid JSON."""
        mock_request.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        mock_response = MagicMock(spec=Response)
        mock_response.status = 400
        mock_response.content_type = "text/plain"

        with patch("agentuity.server.web.Response", return_value=mock_response):
            response = await handle_agent_request(mock_request)

            assert response.status == 400
            assert response.content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_handle_agent_request_exception(self, mock_request):
        """Test agent request handling when an exception occurs."""
        mock_response = MagicMock(spec=Response)
        mock_response.status = 500
        mock_response.content_type = "text/plain"

        with (
            patch("agentuity.server.trace.get_tracer", return_value=MagicMock()),
            patch("agentuity.server.extract", return_value={}),
            patch(
                "agentuity.server.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
            patch("agentuity.server.web.Response", return_value=mock_response),
        ):
            mock_run_agent.side_effect = ValueError("Test error")

            response = await handle_agent_request(mock_request)

            assert response.status == 500
            assert response.content_type == "text/plain"

    def test_inject_trace_context(self):
        """Test inject_trace_context function."""
        headers = {}
        with patch("agentuity.server.inject") as mock_inject:
            inject_trace_context(headers)
            mock_inject.assert_called_once_with(headers)

    def test_inject_trace_context_error(self):
        """Test inject_trace_context handles errors."""
        headers = {}
        with (
            patch("agentuity.server.inject", side_effect=Exception("Test error")),
            patch("agentuity.server.logger.error") as mock_error,
        ):
            inject_trace_context(headers)
            mock_error.assert_called_once()
