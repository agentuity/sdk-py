from typing import Any
from .data import Data


class AgentRequest(dict):
    """
    The request that triggered the agent invocation
    """

    def __init__(self, req: dict):
        self._req = req
        self._data = Data(req)
        super().__init__(req)

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

    def __str__(self) -> str:
        return f"AgentRequest(trigger={self.trigger}, contentType={self._data.contentType}, data={self._data.base64}, metadata={self.metadata})"
