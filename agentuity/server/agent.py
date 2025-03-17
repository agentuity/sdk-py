from .config import AgentConfig
import httpx
from .data import encode_payload, value_to_payload, Data
from typing import Optional, Union
from opentelemetry import trace
from opentelemetry.propagate import inject


class RemoteAgentResponse:
    """
    A container class for responses from remote agent invocations. This class provides
    structured access to the response data, content type, and metadata.
    """

    def __init__(self, data: dict):
        """
        Initialize a RemoteAgentResponse with response data.

        Args:
            data: Dictionary containing:
                - payload: The response data
                - contentType: The MIME type of the response
                - metadata: Optional metadata associated with the response
        """
        self.data = Data(data)
        self.contentType = data.get("contentType", "text/plain")
        self.metadata = data.get("metadata", {})


class RemoteAgent:
    """
    A client for invoking remote agents. This class provides methods to communicate
    with agents running in a separate process, supporting various data types and
    distributed tracing.
    """

    def __init__(self, agentconfig: AgentConfig, port: int, tracer: trace.Tracer):
        """
        Initialize the RemoteAgent client.

        Args:
            agentconfig: Configuration for the remote agent
            port: Port number where the agent is listening
            tracer: OpenTelemetry tracer for distributed tracing
        """
        self.agentconfig = agentconfig
        self._port = port
        self._tracer = tracer

    async def run(
        self,
        data: Union[str, int, float, bool, list, dict, bytes, "Data"],
        base64: bytes = None,
        content_type: str = "text/plain",
        metadata: Optional[dict] = None,
    ) -> RemoteAgentResponse:
        """
        Invoke the remote agent with the provided data.

        Args:
            data: The data to send to the agent. Can be:
                - Data object
                - bytes
                - str, int, float, bool
                - list or dict (will be converted to JSON)
            base64: Optional pre-encoded base64 data to send instead of encoding the data parameter
            content_type: The MIME type of the data (default: "text/plain")
            metadata: Optional metadata to include with the request

        Returns:
            RemoteAgentResponse: The response from the remote agent

        Raises:
            Exception: If the agent invocation fails or returns an error status
        """
        with self._tracer.start_as_current_span("remoteagent.run") as span:
            span.set_attribute("remote.agentId", self.agentconfig.id)
            span.set_attribute("remote.agentName", self.agentconfig.name)
            span.set_attribute("scope", "local")

            p = None
            if data is not None:
                p = value_to_payload(content_type, data)

            invoke_payload = {
                "trigger": "agent",
                "payload": base64 or encode_payload(p["payload"]),
                "metadata": metadata,
                "contentType": p is not None and p["contentType"] or content_type,
            }

            url = f"http://127.0.0.1:{self._port}/{self.agentconfig.id}"
            headers = {}
            inject(headers)

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=invoke_payload, headers=headers)
                if response.status_code != 200:
                    body = response.content.decode("utf-8")
                    span.record_exception(Exception(body))
                    span.set_status(trace.Status(trace.StatusCode.ERROR, body))
                    raise Exception(body)
                data = response.json()
                span.set_status(trace.Status(trace.StatusCode.OK))
                return RemoteAgentResponse(data)

    def __str__(self) -> str:
        """
        Get a string representation of the remote agent.

        Returns:
            str: A formatted string containing the agent configuration
        """
        return f"RemoteAgent(agentconfig={self.agentconfig})"
