import httpx
import json
import os
from typing import Optional, Union
from opentelemetry import trace
from opentelemetry.propagate import inject
import asyncio
import logging
from agentuity import __version__
from .config import AgentConfig
from .data import Data, DataLike, dataLikeToData

# Configurable timeout values
CONNECT_TIMEOUT = float(os.environ.get("AGENTUITY_CONNECT_TIMEOUT", "30.0"))
READ_TIMEOUT = float(os.environ.get("AGENTUITY_READ_TIMEOUT", "300.0"))
WRITE_TIMEOUT = float(os.environ.get("AGENTUITY_WRITE_TIMEOUT", "30.0"))
POOL_TIMEOUT = float(os.environ.get("AGENTUITY_POOL_TIMEOUT", "10.0"))


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


class LocalAgent:
    """
    A client for invoking remote agents locally. This class provides methods to communicate
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
        somedata: "DataLike",
        metadata: Optional[dict] = None,
    ) -> RemoteAgentResponse:
        """
        Invoke the local agent with the provided data.

        Args:
            data: Data object
            metadata: Optional metadata to include with the request

        Returns:
            RemoteAgentResponse: The response from the remote agent

        Raises:
            Exception: If the agent invocation fails or returns an error status
        """
        with self._tracer.start_as_current_span("remoteagent.run") as span:
            span.set_attribute("remote.agentId", self.agentconfig.id)
            span.set_attribute("remote.agentName", self.agentconfig.name)
            span.set_attribute("@agentuity/scope", "local")

            data = dataLikeToData(somedata)

            url = f"http://127.0.0.1:{self._port}/{self.agentconfig.id}"
            headers = {
                "x-agentuity-trigger": "agent",
            }
            inject(headers)
            headers["Content-Type"] = data.content_type
            if metadata is not None:
                for key, value in metadata.items():
                    headers[f"x-agentuity-{key}"] = str(value)

            async def data_generator():
                async for chunk in await data.stream():
                    yield chunk

            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=CONNECT_TIMEOUT,
                        read=READ_TIMEOUT,
                        write=WRITE_TIMEOUT,
                        pool=POOL_TIMEOUT,
                    )
                ) as client:
                    response = await client.post(
                        url, content=data_generator(), headers=headers
                    )
                    span.set_attribute("http.status_code", response.status_code)
                    if response.status_code != 200:
                        body = response.content.decode("utf-8")
                        exception = Exception(body)
                        span.record_exception(exception)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, body))
                        # Log the error but don't call record_exception again
                        logger = logging.getLogger(__name__)
                        logger.error(
                            f"LocalAgent communication failed for {self.agentconfig.id}: {body}"
                        )
                        raise exception

                    stream = await create_stream_reader(response)
                    contentType = response.headers.get(
                        "content-type", "application/octet-stream"
                    )
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return RemoteAgentResponse(
                        Data(contentType, stream), response.headers
                    )
            except Exception as e:
                # Check if this is an HTTP error that was already handled above
                # We can identify HTTP errors by checking if the exception message matches
                # what we would have created for HTTP errors
                if (
                    hasattr(e, "args")
                    and len(e.args) > 0
                    and any(
                        keyword in str(e).lower()
                        for keyword in ["server error", "not found", "unauthorized"]
                    )
                ):
                    # This is likely an HTTP error that was already logged and recorded
                    raise
                else:
                    # This is a different kind of error (network, timeout, etc.)
                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"LocalAgent communication failed for {self.agentconfig.id}: {e}"
                    )
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

    def __str__(self) -> str:
        """
        Get a string representation of the remote agent.

        Returns:
            str: A formatted string containing the agent configuration
        """
        return f"RemoteAgent(agentconfig={self.agentconfig})"


class RemoteAgent:
    def __init__(self, agentconfig: dict, port: int, tracer: trace.Tracer):
        self.agentconfig = agentconfig
        self.port = port
        self.tracer = tracer

    async def run(
        self,
        somedata: "DataLike",
        metadata: Optional[dict] = None,
    ) -> RemoteAgentResponse:
        with self.tracer.start_as_current_span("remoteagent.run") as span:
            span.set_attribute("@agentuity/agentId", self.agentconfig.get("id"))
            span.set_attribute("@agentuity/agentName", self.agentconfig.get("name"))
            span.set_attribute("@agentuity/orgId", self.agentconfig.get("orgId"))
            span.set_attribute(
                "@agentuity/projectId", self.agentconfig.get("projectId")
            )
            span.set_attribute(
                "@agentuity/transactionId",
                self.agentconfig.get("transactionId"),
            )
            span.set_attribute("@agentuity/scope", "remote")

            data = dataLikeToData(somedata)

            headers = {
                "x-agentuity-trigger": "agent",
                "x-agentuity-scope": "remote",
            }
            inject(headers)
            if metadata is not None:
                headers["x-agentuity-metadata"] = json.dumps(metadata)
            headers["Content-Type"] = data.content_type
            headers["Authorization"] = f"Bearer {self.agentconfig.get('authorization')}"
            headers["User-Agent"] = f"Agentuity Python SDK/{__version__}"

            async def data_generator():
                async for chunk in await data.stream():
                    yield chunk

            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=CONNECT_TIMEOUT,
                        read=READ_TIMEOUT,
                        write=WRITE_TIMEOUT,
                        pool=POOL_TIMEOUT,
                    )
                ) as client:
                    response = await client.post(
                        self.agentconfig.get("url"),
                        content=data_generator(),
                        headers=headers,
                    )
                    if response.status_code != 200:
                        error_msg = response.content.decode("utf-8")
                        exception = Exception(error_msg)
                        span.record_exception(exception)
                        span.set_status(
                            trace.Status(
                                trace.StatusCode.ERROR,
                                error_msg,
                            )
                        )
                        # Log the error but don't call record_exception again
                        logger = logging.getLogger(__name__)
                        logger.error(
                            f"RemoteAgent communication failed for {self.agentconfig.get('id')}: {error_msg}"
                        )
                        raise exception

                    stream = await create_stream_reader(response)
                    contentType = response.headers.get(
                        "content-type", "application/octet-stream"
                    )
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return RemoteAgentResponse(
                        Data(contentType, stream), response.headers
                    )
            except Exception as e:
                # Check if this is an HTTP error that was already handled above
                if (
                    hasattr(e, "args")
                    and len(e.args) > 0
                    and "Internal server error" in str(e)
                ):
                    # This is an HTTP error that was already logged and recorded
                    raise
                else:
                    # This is a different kind of error (network, timeout, etc.)
                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"RemoteAgent communication failed for {self.agentconfig.get('id')}: {e}"
                    )
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

    def __str__(self) -> str:
        return f"RemoteAgent(agent={self.agentconfig.get('id')})"


def resolve_agent(context: any, req: Union[dict, str]):
    if isinstance(req, str):
        if req in context.agents_by_id:
            req = {"id": req}
        else:
            req = {"name": req}

    found = None
    if "id" in req and req.get("id") in context.agents_by_id:
        found = context.agents_by_id[req.get("id")]
    else:
        for _, agent in context.agents_by_id.items():
            if "name" in req and agent.get("name") == req.get("name"):
                if (
                    "projectId" in agent
                    and agent["projectId"] == context.projectId
                    or "projectId" not in agent
                ):
                    found = agent
                    break

    if found and found.get("id") == context.agent.id:
        raise ValueError(
            "agent loop detected trying to redirect to the current active agent. if you are trying to redirect to another agent in a different project with the same name, you must specify the projectId parameter along with the name parameter"
        )

    if found:
        return LocalAgent(AgentConfig(found), context.port, context.tracer)

    with context.tracer.start_as_current_span("remoteagent.resolve") as span:
        if "name" in req:
            span.set_attribute("remote.agentName", req.get("name"))
        if "id" in req:
            span.set_attribute("remote.agentId", req.get("id"))

        headers = {
            "Authorization": f"Bearer {context.api_key}",
            "User-Agent": f"Agentuity Python SDK/{__version__}",
        }
        inject(headers)

        response = httpx.post(
            f"{context.base_url}/agent/2025-03-17/resolve",
            headers=headers,
            json=req,
        )
        span.set_attribute("http.status_code", response.status_code)
        name = None
        if "name" in req:
            name = req.get("name")
        elif "id" in req:
            name = req.get("id")
        errmsg = f"agent {name} not found or you don't have access to it"
        if response.status_code == 404:
            span.set_status(
                trace.Status(
                    trace.StatusCode.ERROR,
                    errmsg,
                )
            )
            raise ValueError(errmsg)
        if response.status_code != 200:
            span.set_status(
                trace.Status(
                    trace.StatusCode.ERROR,
                    errmsg,
                )
            )
            raise ValueError(errmsg)
        data = response.json()
        if not data.get("success", False):
            error = data.get("error", "unknown error")
            span.set_status(
                trace.Status(
                    trace.StatusCode.ERROR,
                    error,
                )
            )
            raise Exception(error)
        span.set_status(trace.Status(trace.StatusCode.OK))
        return RemoteAgent(data.get("data"), context.port, context.tracer)


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
