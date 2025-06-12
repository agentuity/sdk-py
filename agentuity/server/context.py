import os
from typing import Union
from logging import Logger
from opentelemetry import trace
from agentuity.otel import create_logger
from .config import AgentConfig
from .agent import LocalAgent, RemoteAgent, resolve_agent
from .vector import VectorStore
from .keyvalue import KeyValueStore
from .objectstore import ObjectStore
from .types import AgentContextInterface
from .util import deprecated


class AgentContext(AgentContextInterface):
    """
    The context of the agent invocation. This class provides access to all the necessary
    services, configuration, and environment information needed during agent execution.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        services: dict,
        logger: Logger,
        tracer: trace.Tracer,
        agent: dict,
        agents_by_id: dict,
        port: int,
        run_id: str,
        scope: str,
    ):
        """
        Initialize the AgentContext with required services and configuration.

        Args:
            base_url: The base URL of the Agentuity Cloud
            api_key: The API key for the Agentuity Cloud
            services: Dictionary containing service instances:
                - kv: Key-value store service
                - vector: Vector store service
            logger: Logging instance for the agent
            tracer: OpenTelemetry tracer for distributed tracing
            agent: Dictionary containing the current agent's configuration
            agents_by_id: Dictionary mapping agent IDs to their configurations
            port: Port number for agent communication
            run_id: The run id for the executing session
            scope: The scope of the agent invocation
        """
        self.port = port
        self._base_url = base_url
        self._api_key = api_key

        """
        the key value store
        """
        self.kv: KeyValueStore = services.get("kv")
        """
        the vector store
        """
        self.vector: VectorStore = services.get("vector")
        """
        the object store
        """
        self.objectstore: ObjectStore = services.get("objectstore")
        """
        the version of the Agentuity SDK
        """
        self.sdkVersion = os.getenv("AGENTUITY_SDK_VERSION", "unknown")
        """
        the run id for the executing session
        """
        self.runId = run_id
        """
        the scope of the agent invocation either local or remote
        """
        self.scope = scope
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
        self.agents_by_id = agents_by_id

    def get_agent(self, agent_id_or_name: str) -> Union["LocalAgent", "RemoteAgent"]:
        """
        Retrieve a LocalAgent instance by its ID or name or a RemoteAgent instance by its ID.

        Args:
            agent_id_or_name: The unique identifier or display name of the agent

        Returns:
            Union["LocalAgent", "RemoteAgent"]: The requested agent instance

        Raises:
            ValueError: If no agent is found with the given ID or name
        """
        return resolve_agent(self, agent_id_or_name)

    @deprecated("Use agent_id instead")
    @property
    def agentId(self) -> str:
        return self.agent.id

    @property
    def agent_id(self) -> str:
        return self.agent.id

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def api_key(self) -> str:
        return self._api_key
