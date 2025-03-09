from typing import Optional
import json

from .data import encode_payload


class AgentResponse:
    """
    The response from an agent invocation. This is a convenience object that can be used to return a response from an agent.
    """

    def __init__(self):
        self.content_type = "text/plain"
        self.payload = ""
        self.metadata = {}

    def handoff(self, agent, args):
        """
        handoff the current request another agent within the same project
        """
        raise NotImplementedError("Handoff is not implemented")

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
