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
    PromptClient,
    PromptCompileResult,
    autostart,
)

from agentuity.io.email import EmailAttachment
from agentuity.io.discord import DiscordMessage
from agentuity.io.telegram import Telegram, parse_telegram
from agentuity.apis.discord import DiscordApi

__all__ = [
    "AgentRequest",
    "AgentResponse",
    "AgentContext",
    "KeyValueStore",
    "VectorStore",
    "ObjectStore",
    "PromptClient",
    "PromptCompileResult",
    "autostart",
    "EmailAttachment",
    "DiscordMessage",
    "Telegram",
    "parse_telegram",
    "DiscordApi",
]
