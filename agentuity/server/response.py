from typing import Optional, Iterable, Callable, Any, Union, AsyncIterator
import json
from opentelemetry import trace
from .agent import RemoteAgent
from asyncio import StreamReader
from .config import AgentConfig
from .data import Data
import asyncio


class AgentResponse:
    """
    The response from an agent invocation. This is a convenience object that can be used to return a response from an agent.
    """

    def __init__(
        self,
        tracer: trace.Tracer,
        agents_by_id: dict,
        port: int,
        data: "Data",
    ):
        """
        Initialize an AgentResponse object.

        Args:
            payload: The initial payload data
            tracer: OpenTelemetry tracer for distributed tracing
            agents_by_id: Dictionary mapping agent IDs to their configurations
            port: Port number for agent communication
        """
        self._contentType = "application/octet-stream"
        self._metadata = {}
        self._tracer = tracer
        self._agents_by_id = agents_by_id
        self._port = port
        self._payload = None
        self._stream = None
        self._transform = None
        self._buffer_read = False
        self._data = data
        self._is_async = False

    @property
    def contentType(self) -> str:
        """
        Get the content type of the data.

        Returns:
            str: The MIME type of the data. If not provided, it will be inferred from
                the data. If it cannot be inferred, returns 'application/octet-stream'
        """
        return self._contentType

    @property
    def metadata(self) -> dict:
        """
        Get the metadata of the data.
        """
        return self._metadata if self._metadata else {}

    async def handoff(
        self, params: dict, args: Optional[dict] = None, metadata: Optional[dict] = None
    ) -> "AgentResponse":
        """
        Handoff the current request to another agent within the same project.

        Args:
            params: Dictionary containing either 'id' or 'name' to identify the target agent
            args: Optional arguments to pass to the target agent
            metadata: Optional metadata to pass to the target agent

        Returns:
            AgentResponse: The response from the target agent

        Raises:
            ValueError: If agent is not found by id or name
        """
        if "id" not in params and "name" not in params:
            raise ValueError("params must have an id or name")

        found_agent = None
        # FIXME check this logic against js sdk
        for id, agent in self._agents_by_id.items():
            if ("id" in params and id == params["id"]) or (
                "name" in agent and agent["name"] == params["name"]
            ):
                found_agent = agent
                break

        # FIXME: this only works if the agent is local, need to handle remote agents
        if found_agent is None:
            raise ValueError("agent not found by id or name")

        agent = RemoteAgent(AgentConfig(found_agent), self._port, self._tracer)

        if not args:
            agent_response = await agent.run(self._data, metadata)
        else:
            # Create a StreamReader from the args data
            reader = asyncio.StreamReader()
            reader.feed_data(json.dumps(args).encode("utf-8"))
            reader.feed_eof()
            # FIXME: need to be any serializable type
            data = Data("application/json", reader)
            agent_response = await agent.run(data, metadata)

        self._metadata = agent_response.metadata
        self._contentType = agent_response.data.contentType
        self._stream = await agent_response.data.stream()

        return self

    def empty(self, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set an empty response with optional metadata.

        Args:
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with empty payload
        """
        self._metadata = metadata
        return self

    def text(self, data: str, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a plain text response.

        Args:
            data: The text content to send
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with text content
        """
        self._contentType = "text/plain"
        self._payload = data
        self._metadata = metadata
        return self

    def html(self, data: str, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set an HTML response.

        Args:
            data: The HTML content to send
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with HTML content
        """
        self._contentType = "text/html"
        self._payload = data
        self._metadata = metadata
        return self

    def json(self, data: dict, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a JSON response.

        Args:
            data: The dictionary to be JSON encoded
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with JSON content
        """
        self._contentType = "application/json"
        self._payload = json.dumps(data)
        self._metadata = metadata
        return self

    def binary(
        self,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None,
    ) -> "AgentResponse":
        """
        Set a binary response with specified content type.

        Args:
            data: The binary data to send
            content_type: The MIME type of the binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with binary content
        """
        self._contentType = content_type
        self._payload = data
        self._metadata = metadata
        return self

    def pdf(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a PDF response.

        Args:
            data: The PDF binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with PDF content
        """
        return self.binary(data, "application/pdf", metadata)

    def png(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a PNG image response.

        Args:
            data: The PNG binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with PNG content
        """
        return self.binary(data, "image/png", metadata)

    def jpeg(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a JPEG image response.

        Args:
            data: The JPEG binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with JPEG content
        """
        return self.binary(data, "image/jpeg", metadata)

    def gif(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a GIF image response.

        Args:
            data: The GIF binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with GIF content
        """
        return self.binary(data, "image/gif", metadata)

    def webp(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a WebP image response.

        Args:
            data: The WebP binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with WebP content
        """
        return self.binary(data, "image/webp", metadata)

    def webm(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a WebM video response.

        Args:
            data: The WebM binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with WebM content
        """
        return self.binary(data, "video/webm", metadata)

    def mp3(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set an MP3 audio response.

        Args:
            data: The MP3 binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with MP3 content
        """
        return self.binary(data, "audio/mpeg", metadata)

    def mp4(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set an MP4 video response.

        Args:
            data: The MP4 binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with MP4 content
        """
        return self.binary(data, "video/mp4", metadata)

    def m4a(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set an M4A audio response.

        Args:
            data: The M4A binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with M4A content
        """
        return self.binary(data, "audio/m4a", metadata)

    def wav(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a WAV audio response.

        Args:
            data: The WAV binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with WAV content
        """
        return self.binary(data, "audio/wav", metadata)

    def ogg(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set an OGG audio response.

        Args:
            data: The OGG binary data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with OGG content
        """
        return self.binary(data, "audio/ogg", metadata)

    def data(
        self, data: Any, content_type: str, metadata: Optional[dict] = None
    ) -> "AgentResponse":
        """
        Set a response with specific data and content type.

        Args:
            data: The data to send (can be any type)
            content_type: The MIME type of the data
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with the specified content
        """
        if isinstance(data, bytes):
            return self.binary(data, content_type, metadata)
        elif isinstance(data, str):
            self._contentType = content_type
            self._payload = data
            self._metadata = metadata
            return self
        elif isinstance(data, dict):
            self._contentType = content_type
            self._payload = json.dumps(data)
            self._metadata = metadata
            return self
        else:
            self._contentType = content_type
            self._payload = str(data)
            self._metadata = metadata
            return self

    def markdown(
        self, content: str, metadata: Optional[dict] = None
    ) -> "AgentResponse":
        """
        Set a markdown response.

        Args:
            content: The markdown content to send
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with markdown content
        """
        self._contentType = "text/markdown"
        self._payload = content
        self._metadata = metadata
        return self

    def stream(
        self,
        data: Union[Iterable[Any], AsyncIterator[Any], "AgentResponse"],
        transform: Optional[Callable[[Any], str]] = None,
        contentType: str = "application/octet-stream",
    ) -> "AgentResponse":
        """
        Sets up streaming response from an iterable data source.

        Args:
            data: An iterable or async iterator containing the data to stream. Can be any type of iterable
                (list, generator, etc.) or async iterator containing any type of data. Also supports
                another AgentResponse object for chaining streams.
            transform: Optional callable function that transforms each item in the stream
                into a string. If not provided, items are returned as-is.
            contentType: The MIME type of the streamed content

        Returns:
            AgentResponse: The response object configured for streaming. The response can
                then be iterated over to yield the streamed data.
        """

        self._contentType = contentType
        self._metadata = None
        self._transform = transform

        if isinstance(data, AgentResponse):
            # If data is an AgentResponse, we'll use its stream directly
            self._stream = data
            self._is_async = True  # AgentResponse is always async
        else:
            self._stream = data
            self._is_async = hasattr(data, "__anext__")
        return self

    @property
    def is_stream(self) -> bool:
        """
        Check if the response is configured for streaming.

        Returns:
            bool: True if the response is a stream, False otherwise
        """
        return self._stream is not None

    def __aiter__(self):
        """
        Make the response object async iterable for streaming.

        Returns:
            AgentResponse: The response object itself as an async iterator
        """
        return self

    async def __anext__(self):
        """
        Get the next item from the stream asynchronously.

        Returns:
            Any: The next item from the stream, transformed if a transform function is set

        Raises:
            StopAsyncIteration: If the stream is exhausted or not configured for streaming
        """
        if self._stream is not None:
            try:
                if isinstance(self._stream, StreamReader):
                    # If stream is an StreamReader, use its __anext__ directly
                    item = await self._stream.__anext__()
                elif self._is_async:
                    item = await self._stream.__anext__()
                else:
                    item = next(self._stream)

                if self._transform:
                    item = self._transform(item)
                if isinstance(item, str):
                    return item.encode("utf-8")
                return item
            except (StopAsyncIteration, StopIteration):
                raise StopAsyncIteration

        if self._buffer_read:
            raise StopAsyncIteration

        self._buffer_read = True
        if isinstance(self._payload, str):
            return self._payload.encode("utf-8")
        return self._payload
