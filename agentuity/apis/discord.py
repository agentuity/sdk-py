import os
import httpx
from opentelemetry import trace
from opentelemetry.propagate import inject
from agentuity import __version__
from agentuity.server.types import DiscordServiceInterface


class DiscordApi(DiscordServiceInterface):
    async def send_reply(
        self,
        agent_id: str,
        message_id: str,
        channel_id: str,
        content: str
    ) -> None:
        tracer = trace.get_tracer("discord")
        with tracer.start_as_current_span("agentuity.discord.reply") as span:
            span.set_attribute("@agentuity/agentId", agent_id)
            span.set_attribute("@agentuity/discordMessageId", message_id)
            span.set_attribute("@agentuity/discordChannelId", channel_id)

            api_key = os.environ.get("AGENTUITY_SDK_KEY") or os.environ.get("AGENTUITY_API_KEY")
            base_url = os.environ.get("AGENTUITY_TRANSPORT_URL", "https://api.agentuity.com")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            inject(headers)

            payload = {
                "content": content,
                "messageId": message_id,
                "channelId": channel_id,
            }

            url = f"{base_url}/discord/{agent_id}/reply"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    raise ValueError(f"Error sending discord reply: {response.text} ({response.status_code})")
