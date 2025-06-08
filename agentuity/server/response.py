from typing import Optional, Iterable, Callable, Any, Union, AsyncIterator
import json
import inspect
from .agent import resolve_agent
from asyncio import StreamReader
from .data import Data, DataLike, dataLikeToData
from .util import deprecated


class AgentResponse:
    """
    The response from an agent invocation. This is a convenience object that can be used to return a response from an agent.
    """

    from .context import AgentContext

    def __init__(
        self,
        context: AgentContext,
        data: "Data",
    ):
        """
        Initialize an AgentResponse object.

        Args:
            context: The context of the agent
            data: The data to send to the agent
        """
        self._contentType = "application/octet-stream"
        self._metadata = {}
        self._tracer = context.tracer
        self._context = context
        self._port = context.port
        self._payload = None
        self._stream = None
        self._transform = None
        self._buffer_read = False
        self._data = data
        self._is_async = False
        self._handoff_params = None  # Store handoff parameters for deferred execution

    @deprecated("Use content_type instead")
    @property
    def contentType(self) -> str:
        """
        Get the content type of the data.

        Returns:
            str: The MIME type of the data. If not provided, it will be inferred from
                the data. If it cannot be inferred, returns 'application/octet-stream'
        """
        return self.content_type

    @property
    def content_type(self) -> str:
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

    def handoff(
        self, params: dict, args: "DataLike" = None, metadata: Optional[dict] = None
    ) -> "AgentResponse":
        """
        Configure a handoff to another agent. Execution is deferred until response processing.

        Args:
            params: Dictionary with 'id' or 'name' to identify target agent
            args: Optional data to pass to target agent (defaults to current data)
            metadata: Optional metadata for target agent

        Returns:
            AgentResponse: Self for method chaining

        Raises:
            ValueError: If params missing both 'id' and 'name'
        """
        if "id" not in params and "name" not in params:
            raise ValueError("params must have an id or name")

        # Store handoff parameters for deferred execution
        self._handoff_params = {"params": params, "args": args, "metadata": metadata}

        return self

    async def _execute_handoff(self):
        """
        Execute the deferred handoff operation. Called internally by framework.

        Returns:
            AgentResponse: Current response updated with target agent's response

        Raises:
            ValueError: If agent not found or not accessible
            Exception: If agent execution fails
        """
        if not self._handoff_params:
            return self

        params = self._handoff_params["params"]
        args = self._handoff_params["args"]
        metadata = self._handoff_params["metadata"]
        agent_id = params.get("id") or params.get("name")

        # Enhanced error handling for agent resolution
        try:
            found_agent = resolve_agent(self._context, params)
        except ValueError as e:
            raise ValueError(
                f"Handoff failed: Agent '{agent_id}' not found or not accessible. {str(e)}"
            ) from e
        except Exception as e:
            raise Exception(
                f"Handoff failed: Error resolving agent '{agent_id}': {str(e)}"
            ) from e

        if found_agent is None:
            raise ValueError(
                f"Handoff failed: Agent '{agent_id}' could not be resolved"
            )

        try:
            # Execute handoff with appropriate data
            if not args:
                agent_response = await found_agent.run(self._data, metadata)
            else:
                data = dataLikeToData(args)
                agent_response = await found_agent.run(data, metadata)

            # Update response with target agent's response
            self._metadata = agent_response.metadata
            self._contentType = agent_response.data.content_type
            stream = await agent_response.data.stream()
            self._stream = stream
            self._is_async = hasattr(self._stream, "__anext__")

            # Clear handoff params after successful execution
            self._handoff_params = None
            return self

        except Exception as e:
            # Handle specific timeout errors more gracefully
            error_msg = str(e)
            if "ReadTimeout" in error_msg or "timeout" in error_msg.lower():
                raise Exception(
                    f"Handoff to agent '{agent_id}' timed out. The target agent may be taking too long to respond or may be unavailable."
                ) from e
            elif "ConnectionError" in error_msg or "connection" in error_msg.lower():
                raise Exception(
                    f"Handoff to agent '{agent_id}' failed due to connection issues. The target agent may be unavailable."
                ) from e
            else:
                raise Exception(
                    f"Handoff execution failed for agent '{agent_id}': {str(e)}"
                ) from e

    @property
    def has_pending_handoff(self) -> bool:
        """
        Check if response has a pending handoff operation.

        Returns:
            bool: True if handoff configured but not yet executed
        """
        return self._handoff_params is not None

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

    def json(self, data: Any, metadata: Optional[dict] = None) -> "AgentResponse":
        """
        Set a JSON response.

        Args:
            data: The dictionary to be JSON encoded
            metadata: Optional metadata to include with the response

        Returns:
            AgentResponse: The response object with JSON content
        """
        self._contentType = "application/json"
        self._metadata = metadata
        try:
            self._payload = json.dumps(data)
        except TypeError:
            if hasattr(data, "__dict__"):
                self._payload = json.dumps(data.__dict__)
            else:
                raise ValueError("data is not JSON serializable") from None
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
            # Check if data is a coroutine, async iterator, or has __anext__ method
            self._is_async = (
                inspect.iscoroutine(data)
                or hasattr(data, "__anext__")
                or inspect.isasyncgen(data)
            )
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
                elif inspect.iscoroutine(self._stream):
                    # If stream is a coroutine, await it directly
                    item = await self._stream
                    # After awaiting a coroutine once, it's exhausted
                    self._stream = None
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
