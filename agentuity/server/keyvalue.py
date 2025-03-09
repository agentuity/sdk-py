import httpx
import base64
import json
from typing import Union, Optional
from .data import DataResult, Data
from agentuity import __version__
from opentelemetry import trace


class KeyValueStore:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        tracer: trace.Tracer,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.tracer = tracer

    async def get(self, name: str, key: str) -> DataResult:
        """
        get a value from the key value storage
        """
        with self.tracer.start_as_current_span("agentuity.keyvalue.get") as span:
            span.set_attribute("name", name)
            span.set_attribute("key", key)
            response = httpx.get(
                f"{self.base_url}/sdk/kv/{name}/{key}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": f"Agentuity Python SDK/{__version__}",
                },
            )
            match response.status_code:
                case 200:
                    span.add_event("hit")
                    span.set_status(trace.StatusCode.OK)
                    return DataResult(
                        Data(
                            {
                                "contentType": response.headers["Content-Type"]
                                or "application/octet-stream",
                                "payload": base64.b64encode(response.content).decode(
                                    "utf-8"
                                ),
                            }
                        )
                    )
                case 404:
                    span.add_event("miss")
                    span.set_status(trace.StatusCode.OK)
                    return DataResult(None)
                case _:
                    span.set_status(trace.StatusCode.ERROR, "Failed to get key value")
                    raise Exception(f"Failed to get key value: {response.status_code}")

    async def set(
        self,
        name: str,
        key: str,
        value: Union[str, int, float, bool, list, dict, bytes, "Data"],
        params: Optional[dict] = None,
    ):
        """
        set a value in the key value storage
        """
        with self.tracer.start_as_current_span("agentuity.keyvalue.set") as span:
            span.set_attribute("name", name)
            span.set_attribute("key", key)
            ttl = None
            if params is None:
                params = {}
                ttl = params.get("ttl", None)
            if ttl is not None and ttl < 60:
                raise ValueError("ttl must be at least 60 seconds")
            content_type = params.get("contentType", None)
            payload = None

            if isinstance(value, Data):
                content_type = content_type or value.contentType
                payload = base64.b64decode(value.base64)
            elif isinstance(value, bytes):
                content_type = content_type or "application/octet-stream"
                payload = value
            elif isinstance(value, (str, int, float, bool)):
                content_type = content_type or "text/plain"
                payload = str(value)
            elif isinstance(value, (list, dict)):
                content_type = content_type or "application/json"
                payload = json.dumps(value)
            else:
                span.set_status(trace.StatusCode.ERROR, "Unsupported value type")
                raise ValueError(f"Unsupported value type: {type(value)}")

            ttlstr = ""
            if ttl is not None:
                ttlstr = f"/{ttl}"
                span.set_attribute("ttl", ttlstr)

            span.set_attribute("contentType", content_type)

            response = httpx.put(
                f"{self.base_url}/sdk/kv/{name}/{key}{ttlstr}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": f"Agentuity Python SDK/{__version__}",
                    "Content-Type": content_type,
                },
                content=payload,
            )

            if response.status_code != 201:
                span.set_status(trace.StatusCode.ERROR, "Failed to set key value")
                raise Exception(f"Failed to set key value: {response.status_code}")
            else:
                span.set_status(trace.StatusCode.OK)

    async def delete(self, name: str, key: str):
        """
        delete a value in the key value storage
        """
        with self.tracer.start_as_current_span("agentuity.keyvalue.delete") as span:
            span.set_attribute("name", name)
            span.set_attribute("key", key)
            response = httpx.delete(
                f"{self.base_url}/sdk/kv/{name}/{key}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": f"Agentuity Python SDK/{__version__}",
                },
            )
            if response.status_code != 200:
                span.set_status(trace.StatusCode.ERROR, "Failed to delete key value")
                raise Exception(f"Failed to delete key value: {response.status_code}")
            else:
                span.set_status(trace.StatusCode.OK)
