import json
from agentuity.server.types import (
    AgentRequestInterface,
    AgentContextInterface,
    DiscordMessageInterface,
)


class DiscordMessage(DiscordMessageInterface):
    def __init__(self, message: str):
        try:
            data = json.loads(message)
            if not self._is_valid_discord_message(data):
                raise ValueError("Invalid discord message format")
            
            self._guild_id = data.get("guildId", "")
            self._channel_id = data["channelId"]
            self._message_id = data["messageId"]
            self._user_id = data["userId"]
            self._username = data["username"]
            self._content = data["content"]
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Failed to parse discord message: {str(e)}") from e

    def _is_valid_discord_message(self, data: dict) -> bool:
        required_keys = ["messageId", "channelId", "userId", "username", "content"]
        return all(key in data and isinstance(data[key], str) for key in required_keys)

    @property
    def guild_id(self) -> str:
        return self._guild_id

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def message_id(self) -> str:
        return self._message_id

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def content(self) -> str:
        return self._content

    async def send_reply(
        self,
        request: AgentRequestInterface,
        context: AgentContextInterface,
        content: str
    ) -> None:
        from agentuity.apis.discord import DiscordApi
        discord_api = DiscordApi()
        await discord_api.send_reply(
            context.agentId,
            self._message_id,
            self._channel_id,
            content
        )

    def __repr__(self) -> str:
        return f"DiscordMessage(id={self.message_id},user={self.username},channel={self.channel_id})"


async def parse_discord_message(data: bytes) -> DiscordMessage:
    try:
        return DiscordMessage(data.decode('utf-8'))
    except Exception as error:
        raise ValueError(f"Failed to parse discord: {str(error)}") from error
