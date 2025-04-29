import pytest
import sys
from unittest.mock import MagicMock, patch
from opentelemetry import trace

sys.modules["openlit"] = MagicMock()

from agentuity.server.context import AgentContext  # noqa: E402
from agentuity.server.config import AgentConfig  # noqa: E402
from agentuity.server.agent import RemoteAgent  # noqa: E402


class TestAgentContext:
    """Test suite for the AgentContext class."""

    @pytest.fixture
    def mock_tracer(self):
        """Create a mock tracer for testing."""
        return MagicMock(spec=trace.Tracer)

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        return {"kv": MagicMock(), "vector": MagicMock()}

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent for testing."""
        return {
            "id": "test_agent",
            "name": "Test Agent",
            "filename": "/path/to/agent.py",
        }

    @pytest.fixture
    def mock_agents_by_id(self):
        """Create a mock agents_by_id dictionary for testing."""
        return {
            "test_agent": {
                "id": "test_agent",
                "name": "Test Agent",
                "filename": "/path/to/agent.py",
            },
            "another_agent": {
                "id": "another_agent",
                "name": "Another Agent",
                "filename": "/path/to/another_agent.py",
            },
        }

    @pytest.fixture
    def agent_context(
        self, mock_services, mock_logger, mock_tracer, mock_agent, mock_agents_by_id
    ):
        """Create an AgentContext instance for testing."""
        with patch("agentuity.server.context.create_logger", return_value=mock_logger):
            return AgentContext(
                services=mock_services,
                logger=mock_logger,
                tracer=mock_tracer,
                agent=mock_agent,
                agents_by_id=mock_agents_by_id,
                port=3000,
            )

    def test_init(
        self, agent_context, mock_services, mock_logger, mock_tracer, mock_agent
    ):
        """Test initialization of AgentContext."""
        assert agent_context.kv == mock_services["kv"]
        assert agent_context.vector == mock_services["vector"]
        assert agent_context.logger == mock_logger
        assert agent_context.tracer == mock_tracer
        assert isinstance(agent_context.agent, AgentConfig)
        assert agent_context.agent.id == mock_agent["id"]
        assert agent_context.agent.name == mock_agent["name"]
        assert len(agent_context.agents) == 2

    def test_environment_variables(self):
        """Test environment variables are correctly set."""
        with (
            patch("agentuity.server.context.create_logger"),
            patch.dict(
                "os.environ",
                {
                    "AGENTUITY_SDK_VERSION": "1.0.0",
                    "AGENTUITY_SDK_DEV_MODE": "true",
                    "AGENTUITY_CLOUD_ORG_ID": "org123",
                    "AGENTUITY_CLOUD_PROJECT_ID": "proj456",
                    "AGENTUITY_CLOUD_DEPLOYMENT_ID": "deploy789",
                    "AGENTUITY_CLI_VERSION": "2.0.0",
                    "AGENTUITY_ENVIRONMENT": "production",
                },
                clear=True,
            ),
        ):
            mock_services = {"kv": MagicMock(), "vector": MagicMock()}
            mock_logger = MagicMock()
            mock_tracer = MagicMock(spec=trace.Tracer)
            mock_agent = {"id": "test_agent", "name": "Test Agent"}
            mock_agents_by_id = {
                "test_agent": {"id": "test_agent", "name": "Test Agent"},
                "another_agent": {"id": "another_agent", "name": "Another Agent"},
            }

            context = AgentContext(
                services=mock_services,
                logger=mock_logger,
                tracer=mock_tracer,
                agent=mock_agent,
                agents_by_id=mock_agents_by_id,
                port=3000,
            )

            assert context.sdkVersion == "1.0.0"
            assert context.devmode == "true"
            assert context.orgId == "org123"
            assert context.projectId == "proj456"
            assert context.deploymentId == "deploy789"
            assert context.cliVersion == "2.0.0"
            assert context.environment == "production"

    def test_environment_variables_defaults(
        self, mock_services, mock_logger, mock_tracer, mock_agent, mock_agents_by_id
    ):
        """Test default values for environment variables."""
        with (
            patch("agentuity.server.context.create_logger", return_value=mock_logger),
            patch.dict("os.environ", {}, clear=True),
        ):
            context = AgentContext(
                services=mock_services,
                logger=mock_logger,
                tracer=mock_tracer,
                agent=mock_agent,
                agents_by_id=mock_agents_by_id,
                port=3000,
            )
            assert context.sdkVersion == "unknown"
            assert context.devmode == "false"
            assert context.orgId == "unknown"
            assert context.projectId == "unknown"
            assert context.deploymentId == "unknown"
            assert context.cliVersion == "unknown"
            assert context.environment == "development"

    def test_get_agent_by_id(self, agent_context, mock_tracer):
        """Test getting an agent by ID."""
        with patch("agentuity.server.context.RemoteAgent") as mock_remote_agent:
            mock_instance = MagicMock(spec=RemoteAgent)
            mock_remote_agent.return_value = mock_instance

            result = agent_context.get_agent("test_agent")

            assert result == mock_instance
            mock_remote_agent.assert_called_once()
            args, kwargs = mock_remote_agent.call_args
            assert args[0].id == "test_agent"
            assert args[1] == 3000
            assert args[2] == mock_tracer

    def test_get_agent_by_name(self, agent_context, mock_tracer):
        """Test getting an agent by name."""
        with patch("agentuity.server.context.RemoteAgent") as mock_remote_agent:
            mock_instance = MagicMock(spec=RemoteAgent)
            mock_remote_agent.return_value = mock_instance

            result = agent_context.get_agent("Another Agent")

            assert result == mock_instance
            mock_remote_agent.assert_called_once()
            args, kwargs = mock_remote_agent.call_args
            assert args[0].id == "another_agent"
            assert args[1] == 3000
            assert args[2] == mock_tracer

    def test_get_agent_not_found(self, agent_context):
        """Test getting a non-existent agent raises ValueError."""
        with pytest.raises(ValueError, match="Agent non_existent_agent not found"):
            agent_context.get_agent("non_existent_agent")
