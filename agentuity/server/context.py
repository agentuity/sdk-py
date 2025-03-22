import os
from logging import Logger
from opentelemetry import trace
from .config import AgentConfig
from .agent import RemoteAgent
from agentuity.otel import create_logger


class AgentContext:
    """
    The context of the agent invocation. This class provides access to all the necessary
    services, configuration, and environment information needed during agent execution.
    """

    def __init__(
        self,
        services: dict,
        logger: Logger,
        tracer: trace.Tracer,
        agent: dict,
        agents_by_id: dict,
        port: int,
    ):
        """
        Initialize the AgentContext with required services and configuration.

        Args:
            services: Dictionary containing service instances:
                - kv: Key-value store service
                - vector: Vector store service
            logger: Logging instance for the agent
            tracer: OpenTelemetry tracer for distributed tracing
            agent: Dictionary containing the current agent's configuration
            agents_by_id: Dictionary mapping agent IDs to their configurations
            port: Port number for agent communication
        """
        self._port = port

        """
        the key value store
        """
        self.kv = services.get("kv")
        """
        the vector store
        """
        self.vector = services.get("vector")
        """
        the version of the Agentuity SDK
        """
        self.sdkVersion = os.getenv("AGENTUITY_SDK_VERSION", "unknown")
        """
        returns true if the agent is running in devmode
        """
        self.devmode = os.getenv("AGENTUITY_SDK_DEV_MODE", "false")
        """
        the org id of the Agentuity Cloud project
        """
        self.orgId = os.getenv("AGENTUITY_CLOUD_ORG_ID", "unknown")
        """
        the project id of the Agentuity Cloud project
        """
        self.projectId = os.getenv("AGENTUITY_CLOUD_PROJECT_ID", "unknown")
        """
        the deployment id of the Agentuity Cloud deployment
        """
        self.deploymentId = os.getenv("AGENTUITY_CLOUD_DEPLOYMENT_ID", "unknown")
        """
        the version of the Agentuity CLI
        """
        self.cliVersion = os.getenv("AGENTUITY_CLI_VERSION", "unknown")
        """
        the environment of the Agentuity Cloud project
        """
        self.environment = os.getenv("AGENTUITY_ENVIRONMENT", "development")
        """
        the logger for the agent
        """
        self.logger = create_logger(
            logger,
            "agent",
            {"@agentuity/agentId": agent["id"], "@agentuity/agentName": agent["name"]},
        )
        """
        the otel tracer
        """
        self.tracer = tracer
        """
        the agent configuration
        """
        self.agent = AgentConfig(agent)
        """
        return a list of all the agents in the project
        """
        self.agents = []
        for agent in agents_by_id.values():
            self.agents.append(AgentConfig(agent))

    def get_agent(self, agent_id_or_name: str) -> "RemoteAgent":
        """
        Retrieve a RemoteAgent instance by its ID or name.

        Args:
            agent_id_or_name: The unique identifier or display name of the agent

        Returns:
            RemoteAgent: The requested agent instance

        Raises:
            ValueError: If no agent is found with the given ID or name
        """
        for agent in self.agents:
            if agent.id == agent_id_or_name or agent.name == agent_id_or_name:
                return RemoteAgent(agent, self._port, self.tracer)
        raise ValueError(f"Agent {agent_id_or_name} not found")
