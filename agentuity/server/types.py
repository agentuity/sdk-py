from datetime import datetime
from typing import Any, Optional

from opentelemetry import trace


class AgentRequest:
    def __init__(self, data: dict):
        self._data = data

    @property
    def trigger(self) -> str:
        return self._data.get("trigger", "")

    @property
    def text(self) -> str:
        return self._data.get("text") or self.trigger

    @property
    def id(self) -> str:
        return self._data.get("id") or self._data.get("runId", "")

    def validate(self) -> bool:
        if not self.id:
            raise ValueError("Request must contain 'id' field")
        if not self.trigger and not self.text:
            raise ValueError("Request requires either trigger or text input")
        return True

    def metadata(self, key: str, default: Any = None) -> Any:
        return self._data.get("metadata", {}).get(key, default)

    def json(self) -> dict:
        return self._data.get("payload", {})


class AgentResponse:
    def __init__(self):
        self.content_type = "application/json"
        self.payload = {
            "data": None,
            "metadata": {},
            "timestamps": {"created": datetime.now().isoformat() + "Z"},
        }
        self.metadata = {}

    def _base_response(self, data: Any) -> dict:
        return {
            **self.payload,
            "data": data,
            "metadata": self.metadata,
            "id": str(id(self)),
        }

    def json(self, data: dict, metadata: Optional[dict] = None) -> "AgentResponse":
        self.content_type = "application/json"
        self.payload = self._base_response(data)
        if metadata:
            self.metadata.update(metadata)
        return self

    def error(self, message: str, code: int) -> "AgentResponse":
        self.content_type = "application/json"
        self.payload = self._base_response(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "timestamp": datetime.now().isoformat() + "Z",
                }
            }
        )
        return self


class AgentContext:
    def __init__(self, services: dict, logger: Any, tracer: trace.Tracer, request: Any):
        self.services = services
        self.logger = logger
        self.tracer = tracer
        self.request = request
        self.run_id = str(request.id)
        self.start_time = datetime.now()
        self.timers = {}
