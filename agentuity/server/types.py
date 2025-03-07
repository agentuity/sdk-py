from typing import Any, Optional
import base64
import json
from opentelemetry import trace
import os

"""
Format of the incoming request is:

{
    "trigger": "webhook|manual|sms|email|etc...",
    "payload": "base64 encoded payload",
    "contentType": "content-type of the payload",
    "metadata": {}
}

"""


def decode_payload(payload: str) -> str:
    return base64.b64decode(payload).decode("utf-8")


def decode_payload_bytes(payload: str) -> bytes:
    return base64.b64decode(payload)


class AgentRequest:
    def __init__(self, data: dict):
        self._data = data

    def validate(self) -> bool:
        if not self.contentType:
            raise ValueError("Request must contain 'contentType' field")
        if not self.trigger:
            raise ValueError("Request requires 'trigger' field")
        return True

    @property
    def payload(self) -> str:
        return decode_payload(self._data.get("payload", ""))

    @property
    def contentType(self) -> str:
        return self._data.get("contentType", "application/octet-stream")

    @property
    def trigger(self) -> str:
        return self._data.get("trigger", "")

    @property
    def metadata(self) -> dict:
        return self._data.get("metadata", {})

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    @property
    def text(self) -> str:
        return self.payload if self.contentType == "text/plain" else ""

    def json(self) -> dict:
        if "json" in self.contentType:
            return json.loads(self.payload)
        return {}

    def binary(self) -> bytes:
        return decode_payload_bytes(self.payload)

    def pdf(self) -> bytes:
        return decode_payload_bytes(self.payload) if "pdf" in self.contentType else None

    def png(self) -> bytes:
        return (
            decode_payload_bytes(self.payload)
            if "image/png" in self.contentType
            else None
        )

    def gif(self) -> bytes:
        return (
            decode_payload_bytes(self.payload)
            if "image/gif" in self.contentType
            else None
        )

    def jpeg(self) -> bytes:
        return (
            decode_payload_bytes(self.payload)
            if "image/jpeg" == self.contentType or "image/jpg" == self.contentType
            else None
        )

    def webp(self) -> bytes:
        return (
            decode_payload_bytes(self.payload)
            if "image/webp" == self.contentType
            else None
        )

    def webm(self) -> bytes:
        return (
            decode_payload_bytes(self.payload)
            if "video/webm" == self.contentType
            else None
        )

    def mp3(self) -> bytes:
        return (
            decode_payload_bytes(self.payload)
            if "audio/mpeg" == self.contentType
            else None
        )

    def mp4(self) -> bytes:
        return decode_payload_bytes(self.payload) if "mp4" == self.contentType else None

    def m4a(self) -> bytes:
        return decode_payload_bytes(self.payload) if "m4a" == self.contentType else None

    def wav(self) -> bytes:
        return (
            decode_payload_bytes(self.payload)
            if "audio/wav" == self.contentType
            else None
        )

    def ogg(self) -> bytes:
        return (
            decode_payload_bytes(self.payload)
            if "audio/ogg" == self.contentType
            else None
        )


class AgentResponse:
    def __init__(self):
        self.content_type = "text/plain"
        self.payload = None
        self.metadata = {}

    def empty(self, metadata: Optional[dict] = None) -> "AgentResponse":
        self.metadata = metadata
        return self

    def text(self, data: str, metadata: Optional[dict] = None) -> "AgentResponse":
        self.content_type = "text/plain"
        self.payload = base64.b64encode(data.encode("utf-8")).decode("utf-8")
        self.metadata = metadata
        return self

    def html(self, data: str, metadata: Optional[dict] = None) -> "AgentResponse":
        self.content_type = "text/html"
        self.payload = base64.b64encode(data.encode("utf-8")).decode("utf-8")
        self.metadata = metadata
        return self

    def json(self, data: dict, metadata: Optional[dict] = None) -> "AgentResponse":
        self.content_type = "application/json"
        self.payload = base64.b64encode(json.dumps(data).encode("utf-8")).decode(
            "utf-8"
        )
        self.metadata = metadata
        return self

    def binary(
        self,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None,
    ) -> "AgentResponse":
        self.content_type = content_type
        self.payload = base64.b64encode(data).decode("utf-8")
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


class AgentContext:
    def __init__(
        self, services: dict, logger: Any, tracer: trace.Tracer, request: "AgentRequest"
    ):
        self.request = request
        self.services = services
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

        # TODO:

        """
        the agent configuration
        """
        self.agent = {}
        """
        return a list of all the agents in the project
        """
        self.agents = []
