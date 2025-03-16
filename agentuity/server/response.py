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
        self.content_type = "text/plain"
        self.payload = ""
        self.metadata = {}
        self._payload = payload
        self._tracer = tracer
        self._agents_by_id = agents_by_id
        self._port = port

    async def handoff(
        self, params: dict, args: Optional[dict] = None, metadata: Optional[dict] = None
    ) -> "AgentResponse":
        """
        handoff the current request another agent within the same project
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
        self.metadata = metadata
        return self

    def text(self, data: str, metadata: Optional[dict] = None) -> "AgentResponse":
        self.content_type = "text/plain"
        self.payload = encode_payload(data)
        self.metadata = metadata
        return self

    def html(self, data: str, metadata: Optional[dict] = None) -> "AgentResponse":
        self.content_type = "text/html"
        self.payload = encode_payload(data)
        self.metadata = metadata
        return self

    def json(self, data: dict, metadata: Optional[dict] = None) -> "AgentResponse":
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
        self.content_type = content_type
        self.payload = encode_payload(data)
        self.metadata = metadata
        return self

    def pdf(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "application/pdf", metadata)

    def png(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "image/png", metadata)

    def jpeg(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "image/jpeg", metadata)

    def gif(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "image/gif", metadata)

    def webp(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "image/webp", metadata)

    def webm(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "video/webm", metadata)

    def mp3(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "audio/mpeg", metadata)

    def mp4(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "video/mp4", metadata)

    def m4a(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "audio/m4a", metadata)

    def wav(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "audio/wav", metadata)

    def ogg(self, data: bytes, metadata: Optional[dict] = None) -> "AgentResponse":
        return self.binary(data, "audio/ogg", metadata)

    def stream(
        self, data: Iterable[Any], transform: Callable[[Any], str]
    ) -> "AgentResponse":
        self.content_type = "text/plain"
        self.payload = ""
        self.metadata = None
        self._stream = data
        self._transform = transform
        return self

    @property
    def is_stream(self) -> bool:
        return self._stream is not None

    def __iter__(self):
        if not self.is_stream:
            raise StopIteration
        return self

    def __next__(self):
        if not self.is_stream:
            raise StopIteration
        return self._transform(next(self._stream))
