from typing import Optional, Iterable, Callable, Any
import json
from opentelemetry import trace
from .data import encode_payload
from .agent import RemoteAgent
from .config import AgentConfig


class AgentResponse:
    """
    The response from an agent invocation. This is a convenience object that can be used to return a response from an agent.
    """

    def __init__(
        self, payload: dict, tracer: trace.Tracer, agents_by_id: dict, port: int
    ):
        """
        Initialize an AgentResponse object.

        Args:
            payload: The initial payload data
            tracer: OpenTelemetry tracer for distributed tracing
            agents_by_id: Dictionary mapping agent IDs to their configurations
            port: Port number for agent communication
        """
        self.content_type = "text/plain"
        self.payload = ""
        self.metadata = {}
        self._payload = payload
        self._tracer = tracer
        self._agents_by_id = agents_by_id
        self._port = port
        self._stream = None
        self._transform = None

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
            data = await agent.run(
                base64=self._payload.get("payload", ""),
                metadata=self._payload.get("metadata", {}),
                content_type=self._payload.get("contentType", "text/plain"),
            )
        else:
            data = await agent.run(data=args, metadata=metadata)

        self.content_type = data.contentType
        self.payload = data.data.base64
        self.metadata = data.metadata

        return self

    def empty(self, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set an empty response with optional metadata.

        Args:
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with empty payload
        """
        self.metadata = metadata
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
        self.content_type = "text/plain"
        self.payload = encode_payload(data)
        self.metadata = metadata
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
        self.content_type = "text/html"
        self.payload = encode_payload(data)
        self.metadata = metadata
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
        self.content_type = "application/json"
        self.payload = encode_payload(json.dumps(data))
        self.metadata = metadata
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
        self.content_type = content_type
        self.payload = encode_payload(data)
        self.metadata = metadata
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
        self, 
        data: Any, 
        content_type: str, 
        metadata: Optional[dict] = None
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
            self.content_type = content_type
            self.payload = encode_payload(data)
            self.metadata = metadata
            return self
        elif isinstance(data, dict):
            self.content_type = content_type
            self.payload = encode_payload(json.dumps(data))
            self.metadata = metadata
            return self
        else:
            self.content_type = content_type
            self.payload = encode_payload(str(data))
            self.metadata = metadata
            return self
            
    def markdown(self, content: str, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a markdown response.

        Args:
            content: The markdown content to send
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with markdown content
        """
        self.content_type = "text/markdown"
        self.payload = encode_payload(content)
        self.metadata = metadata
        return self

    def stream(
        self, data: Iterable[Any], transform: Optional[Callable[[Any], str]] = None
    ) -> "AgentResponse":
        """
        Sets up streaming response from an iterable data source.

        Args:
            data: An iterable containing the data to stream. Can be any type of iterable
                (list, generator, etc.) containing any type of data.
            transform: Optional callable function that transforms each item in the stream
                into a string. If not provided, items are returned as-is.

        Returns:
            AgentResponse: The response object configured for streaming. The response can
                then be iterated over to yield the streamed data.

        Example:
            >>> response.stream([1, 2, 3], transform=str)
            >>> for item in response:
            ...     print(item)
        """
        self.content_type = "text/plain"
        self.payload = ""
        self.metadata = None
        self._stream = data
        self._transform = transform
        return self

    @property
    def is_stream(self) -> bool:
        """
        Check if the response is configured for streaming.

        Returns:
            bool: True if the response is a stream, False otherwise
        """
        return self._stream is not None

    def __iter__(self):
        """
        Make the response object iterable for streaming.

        Returns:
            AgentResponse: The response object itself as an iterator

        Raises:
            StopIteration: If the response is not configured for streaming
        """
        if not self.is_stream:
            raise StopIteration
        return self

    def __next__(self):
        """
        Get the next item from the stream.

        Returns:
            Any: The next item from the stream, transformed if a transform function is set

        Raises:
            StopIteration: If the stream is exhausted or not configured for streaming
        """
        if not self.is_stream:
            raise StopIteration
        if self._transform:
            return self._transform(next(self._stream))
        return next(self._stream)
