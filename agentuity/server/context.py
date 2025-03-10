from typing import Any
import os
from opentelemetry import trace
from .config import AgentConfig
from .agent import RemoteAgent


class AgentContext:
    """
    the context of the agent invocation
    """

    def __init__(
        self,
        services: dict,
        logger: Any,
        tracer: trace.Tracer,
        agent: dict,
        agents_by_id: dict,
        port: int,
    ):
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
        the logger
        """
        self.logger = logger
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
        for agent in self.agents:
            if agent.id == agent_id_or_name or agent.name == agent_id_or_name:
                return RemoteAgent(agent, self._port, self.tracer)
        raise ValueError(f"Agent {agent_id_or_name} not found")
