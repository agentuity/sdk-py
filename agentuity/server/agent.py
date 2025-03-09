from .config import AgentConfig
import httpx
from .data import encode_payload, value_to_payload, Data
from typing import Optional, Union


class RemoteAgentResponse:
    def __init__(self, data: dict):
        self.data = Data(data)
        self.contentType = data.get("contentType", "text/plain")
        self.metadata = data.get("metadata", {})


class RemoteAgent:
    def __init__(self, agentconfig: AgentConfig, port: int):
        self.agentconfig = agentconfig
        self._port = port

    async def run(
        self,
        data: Union[str, int, float, bool, list, dict, bytes, "Data"],
        base64: bytes = None,
        content_type: str = "text/plain",
        metadata: Optional[dict] = None,
    ) -> RemoteAgentResponse:
        p = None
        if data is not None:
            p = value_to_payload(content_type, data)

        invoke_payload = {
            "trigger": "agent",
            "payload": base64 or encode_payload(p["payload"]),
            "metadata": metadata,
            "contentType": p is not None and p["contentType"] or content_type,
        }

        url = f"http://127.0.0.1:{self._port}/{self.agentconfig.id}"

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=invoke_payload)
            if response.status_code != 200:
                body = response.content.decode("utf-8")
                raise Exception(body)
            data = response.json()
            return RemoteAgentResponse(data)

    def __str__(self) -> str:
        return f"RemoteAgent(agentconfig={self.agentconfig})"
