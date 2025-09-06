from abc import ABC, abstractmethod
from datetime import datetime
from typing import IO, List, Any, Union, Iterator, AsyncIterator
from aiohttp import StreamReader

DataLike = Union[
    str,
    int,
    float,
    bool,
    list,
    dict,
    bytes,
    "DataInterface",
    StreamReader,
    Iterator[bytes],
    AsyncIterator[bytes],
]


class AgentRequestInterface(ABC):
    @property
    @abstractmethod
    def data(self) -> "DataInterface":
        pass

    @property
    @abstractmethod
    def trigger(self) -> str:
        pass

    @property
    @abstractmethod
    def metadata(self) -> dict:
        pass

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass


class AgentContextInterface(ABC):
    @property
    @abstractmethod
    def agentId(self) -> str:
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        pass

    @property
    @abstractmethod
    def api_key(self) -> str:
        pass


class DataInterface(ABC):
    @property
    @abstractmethod
    def content_type(self) -> str:
        pass

    @abstractmethod
    async def stream(self) -> IO[bytes]:
        pass

    @abstractmethod
    async def text(self) -> str:
        pass

    @abstractmethod
    async def json(self) -> dict:
        pass

    @abstractmethod
    async def binary(self) -> bytes:
        pass

    @abstractmethod
    async def base64(self) -> str:
        pass

    @abstractmethod
    async def email(self) -> "EmailInterface":
        pass

    @abstractmethod
    async def discord(self) -> "DiscordMessageInterface":
        pass

    @abstractmethod
    async def telegram(self) -> "TelegramMessageInterface":
        pass
        
    @abstractmethod
    async def slack(self) -> "SlackMessageInterface":
        pass


class OutgoingEmailAttachmentInterface(ABC):
    @property
    @abstractmethod
    def filename(self) -> str:
        pass

    @abstractmethod
    def data(self) -> "DataLike":
        pass


class EmailAttachmentInterface(ABC):
    @property
    @abstractmethod
    def filename(self) -> str:
        pass

    @abstractmethod
    def data(self) -> "DataInterface":
        pass


class EmailInterface(ABC):
    @property
    @abstractmethod
    def subject(self) -> str | None:
        pass

    @property
    @abstractmethod
    def from_email(self) -> str | None:
        pass

    @property
    @abstractmethod
    def from_name(self) -> str | None:
        pass

    @property
    @abstractmethod
    def to(self) -> str | None:
        pass

    @property
    @abstractmethod
    def date(self) -> datetime | None:
        pass

    @property
    @abstractmethod
    def message_id(self) -> str | None:
        pass

    @property
    @abstractmethod
    def headers(self) -> dict[str, str]:
        pass

    @property
    @abstractmethod
    def text(self) -> str:
        pass

    @property
    @abstractmethod
    def html(self) -> str:
        pass

    @property
    @abstractmethod
    def attachments(self) -> list["EmailAttachmentInterface"]:
        pass

    @abstractmethod
    async def sendReply(
        self,
        request: "AgentRequestInterface",
        context: "AgentContextInterface",
        subject: str = None,
        text: str = None,
        html: str = None,
        attachments: List["OutgoingEmailAttachmentInterface"] = None,
    ):
        pass


class DiscordMessageInterface(ABC):
    @property
    @abstractmethod
    def guild_id(self) -> str:
        pass

    @property
    @abstractmethod
    def channel_id(self) -> str:
        pass

    @property
    @abstractmethod
    def message_id(self) -> str:
        pass

    @property
    @abstractmethod
    def user_id(self) -> str:
        pass

    @property
    @abstractmethod
    def username(self) -> str:
        pass

    @property
    @abstractmethod
    def content(self) -> str:
        pass

    @abstractmethod
    async def send_reply(
        self,
        request: "AgentRequestInterface",
        context: "AgentContextInterface",
        content: str,
    ) -> None:
        pass


class DiscordServiceInterface(ABC):
    @abstractmethod
    async def send_reply(
        self, agent_id: str, message_id: str, channel_id: str, content: str
    ) -> None:
        pass


class TelegramMessageInterface(ABC):
    @property
    @abstractmethod
    def message_id(self) -> int:
        pass

    @property
    @abstractmethod
    def chat_id(self) -> int:
        pass

    @property
    @abstractmethod
    def chat_type(self) -> str:
        pass

    @property
    @abstractmethod
    def from_id(self) -> int:
        pass

    @property
    @abstractmethod
    def from_username(self) -> str | None:
        pass

    @property
    @abstractmethod
    def from_first_name(self) -> str:
        pass

    @property
    @abstractmethod
    def from_last_name(self) -> str | None:
        pass

    @property
    @abstractmethod
    def text(self) -> str:
        pass

    @property
    @abstractmethod
    def date(self) -> int:
        pass

    @abstractmethod
    async def send_reply(
        self,
        request: "AgentRequestInterface",
        context: "AgentContextInterface",
        reply: str,
        options: dict = None,
    ) -> None:
        pass

    @abstractmethod
    async def send_typing(
        self,
        request: "AgentRequestInterface",
        context: "AgentContextInterface",
    ) -> None:
        pass


class TelegramServiceInterface(ABC):
    @abstractmethod
    async def send_reply(
        self, agent_id: str, chat_id: int, message_id: int, reply: str, options: dict = None
    ) -> None:
        pass


class SlackMessageInterface(ABC):
    @property
    @abstractmethod
    def message_type(self) -> str:
        pass

    @property
    @abstractmethod
    def token(self) -> str:
        pass

    @property
    @abstractmethod
    def team_id(self) -> str:
        pass

    @property
    @abstractmethod
    def text(self) -> str:
        pass

    @property
    @abstractmethod
    def user(self) -> str:
        pass

    @property
    @abstractmethod
    def channel(self) -> str:
        pass

    @abstractmethod
    async def send_reply(
        self,
        request: "AgentRequestInterface",
        context: "AgentContextInterface",
        reply: str,
        options: dict = None,
    ) -> None:
        pass


class SlackServiceInterface(ABC):
    @abstractmethod
    async def send_reply(
        self, agent_id: str, channel: str, text: str, options: dict = None
    ) -> None:
        pass
