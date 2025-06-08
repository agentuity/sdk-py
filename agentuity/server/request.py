from typing import Any
from aiohttp import StreamReader
from .types import AgentRequestInterface, DataInterface
from .data import Data


class AgentRequest(AgentRequestInterface):
    """
    The request that triggered the agent invocation.
    """

    def __init__(
        self, trigger: str, metadata: dict, contentType: str, stream: StreamReader
    ):
        """
        Initialize an AgentRequest object.

        Args:
            trigger: The event that triggered this request
            metadata: Optional metadata associated with the request
            contentType: The MIME type of the request data
            stream: The stream of request data
        """
        self._trigger = trigger
        self._metadata = metadata

        self._data = Data(contentType, stream)

    def _get_data(self) -> "DataInterface":
        return self._data

    @property
    def data(self) -> "DataInterface":
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
        return self._trigger

    @property
    def metadata(self) -> dict:
        """
        Get the metadata associated with the request.

        Returns:
            dict: Dictionary containing any additional metadata associated with the request.
                Returns an empty dictionary if no metadata is present.
        """
        return self._metadata

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
        return self._metadata.get(key, default)

    def __str__(self) -> str:
        """
        Get a string representation of the request.

        Returns:
            str: A formatted string containing the request's trigger, content type,
                and metadata
        """
        return f"AgentRequest(trigger={self.trigger},contentType={self._data.content_type},metadata={self.metadata})"
