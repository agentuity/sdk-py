from typing import Any, Optional
import base64
import json
import os
from opentelemetry import trace

"""
Format of the incoming request is:

{
    "trigger": "webhook|manual|sms|email|etc...",
    "payload": "base64 encoded payload",
    "contentType": "content-type of the payload",
    "metadata": {}
}

"""


class DataResult:
    def __init__(self, data: Optional["Data"] = None):
        self._data = data

    @property
    def data(self) -> "Data":
        """
        the data from the result of the operation
        """
        return self._data

    @property
    def exists(self) -> bool:
        """
        true if the data was found
        """
        return self._data is not None

    def __str__(self) -> str:
        return f"DataResult(contentType={self._data.contentType}, payload={self._data.base64})"


class AgentConfig:
    """
    the config for the agent
    """

    def __init__(self, config: dict):
        self._config = config

    @property
    def id(self) -> str:
        """
        the unique id of the agent
        """
        return self._config.get("id")

    @property
    def name(self) -> str:
        """
        the name of the agent
        """
        return self._config.get("name")

    @property
    def description(self) -> str:
        """
        the description of the agent
        """
        return self._config.get("description")

    @property
    def filename(self) -> str:
        """
        the file name to the agent relative to the dist directory
        """
        return self._config.get("filename")

    def __str__(self) -> str:
        return f"AgentConfig(id={self.id}, name={self.name}, description={self.description}, filename={self.filename})"


class Data:
    """
    Data is a container class for working with the payload of an agent data
    """

    def __init__(self, data: dict):
        self._data = data

    @property
    def contentType(self) -> str:
        """
        the content type of the data such as 'text/plain', 'application/json', 'image/png', etc. if no content type is provided, it will be inferred from the data.
        if it cannot be inferred, it will be 'application/octet-stream'.
        """
        return self._data.get("contentType", "application/octet-stream")

    @property
    def base64(self) -> str:
        """
        base64 encoded string of the data
        """
        return self._data.get("payload", "")

    @property
    def text(self) -> bytes:
        """
        the data represented as a string
        """
        return decode_payload(self.base64)

    @property
    def json(self) -> dict:
        """
        the JSON data. If the data is not JSON, this will throw a ValueError.
        """
        try:
            return json.loads(self.text)
        except Exception as e:
            raise ValueError("Data is not JSON") from e

    @property
    def binary(self) -> bytes:
        """
        the binary data represented as a bytes object
        """
        return decode_payload_bytes(self.base64)


def decode_payload(payload: str) -> str:
    return base64.b64decode(payload).decode("utf-8")


def decode_payload_bytes(payload: str) -> bytes:
    return base64.b64decode(payload)


def encode_payload(data: str) -> str:
    return base64.b64encode(data.encode("utf-8")).decode("utf-8")


class AgentRequest:
    """
    The request that triggered the agent invocation
    """

    def __init__(self, req: dict):
        self._req = req
        self._data = Data(req)

    def validate(self) -> bool:
        if not self._req.get("contentType"):
            raise ValueError("Request must contain 'contentType' field")
        if not self._req.get("trigger"):
            raise ValueError("Request requires 'trigger' field")
        return True

    @property
    def data(self) -> "Data":
        """
        get the data of the request
        """
        return self._data

    @property
    def trigger(self) -> str:
        """
        get the trigger of the request
        """
        return self._req.get("trigger")

    @property
    def metadata(self) -> dict:
        """
        get the metadata of the request
        """
        return self._req.get("metadata", {})

    def get(self, key: str, default: Any = None) -> Any:
        """
        get a value from the metadata of the request
        """
        return self.metadata.get(key, default)


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


class AgentContext:
    def __init__(
        self,
        services: dict,
        logger: Any,
        tracer: trace.Tracer,
        agent: dict,
        agents_by_id: dict,
    ):
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
