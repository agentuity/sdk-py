import httpx
import json
from typing import Optional
from opentelemetry import trace
from opentelemetry.propagate import inject
import asyncio

from .config import AgentConfig
from .data import Data


class RemoteAgentResponse:
    """
    A container class for responses from remote agent invocations. This class provides
    structured access to the response data, content type, and metadata.
    """

    def __init__(self, data: Data, headers: dict = None):
        """
        Initialize a RemoteAgentResponse with response data.

        Args:
            data: Data object
        """
        self.data = data
        self.metadata = {}
        if headers is not None:
            for key, value in headers.items():
                if key.startswith("x-agentuity-"):
                    if key == "x-agentuity-metadata":
                        try:
                            self.metadata = json.loads(value)
                        except json.JSONDecodeError:
                            self.metadata = value
                    else:
                        self.metadata[key[12:]] = value


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
        data: "Data",
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

            url = f"http://127.0.0.1:{self._port}/{self.agentconfig.id}"
            headers = {}
            inject(headers)
            headers["Content-Type"] = data.contentType
            if metadata is not None:
                for key, value in metadata.items():
                    headers[f"x-agentuity-{key}"] = str(value)

            async def data_generator():
                async for chunk in await data.stream():
                    yield chunk

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, content=data_generator(), headers=headers
                )
                if response.status_code != 200:
                    body = response.content.decode("utf-8")
                    span.record_exception(Exception(body))
                    span.set_status(trace.Status(trace.StatusCode.ERROR, body))
                    raise Exception(body)

                stream = await create_stream_reader(response)
                contentType = response.headers.get(
                    "content-type", "application/octet-stream"
                )
                span.set_status(trace.Status(trace.StatusCode.OK))
                return RemoteAgentResponse(Data(contentType, stream), response.headers)

    def __str__(self) -> str:
        """
        Get a string representation of the remote agent.

        Returns:
            str: A formatted string containing the agent configuration
        """
        return f"RemoteAgent(agentconfig={self.agentconfig})"


async def create_stream_reader(response):
    reader = asyncio.StreamReader()

    async def feed_reader():
        try:
            async for chunk in response.aiter_bytes():
                reader.feed_data(chunk)
        finally:
            reader.feed_eof()

    # Start feeding the reader in the background
    asyncio.create_task(feed_reader())

    return reader
