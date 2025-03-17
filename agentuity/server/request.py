from typing import Any
from .data import Data


class AgentRequest(dict):
    """
    The request that triggered the agent invocation. This class extends dict to provide
    additional functionality for handling agent requests while maintaining dictionary-like
    behavior.
    """

    def __init__(self, req: dict):
        """
        Initialize an AgentRequest object.

        Args:
            req: Dictionary containing the request data with required fields:
                - contentType: The MIME type of the request data
                - trigger: The event that triggered this request
                - data: The actual request data
                - metadata: Optional metadata associated with the request
        """
        self._req = req
        self._data = Data(req)
        super().__init__(req)

    def validate(self) -> bool:
        """
        Validate that the request contains all required fields.

        Returns:
            bool: True if validation passes

        Raises:
            ValueError: If required fields 'contentType' or 'trigger' are missing
        """
        if not self._req.get("contentType"):
            raise ValueError("Request must contain 'contentType' field")
        if not self._req.get("trigger"):
            raise ValueError("Request requires 'trigger' field")
        return True

    @property
    def data(self) -> "Data":
        """
        Get the data object associated with the request.

        Returns:
            Data: The request data object containing the actual content and its type
        """
        return self._data

    @property
    def trigger(self) -> str:
        """
        Get the trigger that initiated this request.

        Returns:
            str: The trigger identifier that caused this request to be processed
        """
        return self._req.get("trigger")

    @property
    def metadata(self) -> dict:
        """
        Get the metadata associated with the request.

        Returns:
            dict: Dictionary containing any additional metadata associated with the request.
                Returns an empty dictionary if no metadata is present.
        """
        return self._req.get("metadata", {})

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the request metadata.

        Args:
            key: The key to look up in the metadata
            default: Default value to return if the key is not found

        Returns:
            Any: The value associated with the key in metadata, or the default value
                if the key is not found
        """
        return self.metadata.get(key, default)

    def __str__(self) -> str:
        """
        Get a string representation of the request.

        Returns:
            str: A formatted string containing the request's trigger, content type,
                data, and metadata
        """
        return f"AgentRequest(trigger={self.trigger}, contentType={self._data.contentType}, data={self._data.base64}, metadata={self.metadata})"
