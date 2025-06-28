import importlib.metadata

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"

from agentuity.server import (
    AgentRequest,
    AgentResponse,
    AgentContext,
    KeyValueStore,
    VectorStore,
    ObjectStore,
    autostart,
)

from agentuity.server.prompts import (
    PromptLibrary,
    InvalidPromptNameError,
    MissingVariableError,
    PromptNotFoundError,
    PromptExistsError,
)

from agentuity.io.email import EmailAttachment

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "AgentContext",
    "KeyValueStore",
    "VectorStore",
    "ObjectStore",
    "autostart",
    "EmailAttachment",
    "PromptLibrary",
    "InvalidPromptNameError",
    "MissingVariableError",
    "PromptNotFoundError",
    "PromptExistsError",
]
