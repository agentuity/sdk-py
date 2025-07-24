import os
import httpx
from opentelemetry import trace
from opentelemetry.propagate import inject
from agentuity import __version__
from agentuity.server.types import TelegramServiceInterface


class TelegramApi(TelegramServiceInterface):
    async def send_reply(
        self, agent_id: str, chat_id: int, message_id: int, reply: str, options: dict = None
    ) -> None:
        if options is None:
            options = {}
            
        tracer = trace.get_tracer("telegram")
        with tracer.start_as_current_span("agentuity.telegram.reply") as span:
            span.set_attribute("@agentuity/agentId", agent_id)
            span.set_attribute("@agentuity/telegramMessageId", message_id)
            span.set_attribute("@agentuity/telegramChatId", chat_id)

            api_key = os.environ.get("AGENTUITY_SDK_KEY") or os.environ.get(
                "AGENTUITY_API_KEY"
            )
            if not api_key:
                raise ValueError(
                    "API key is required but not found. Set AGENTUITY_SDK_KEY or AGENTUITY_API_KEY environment variable."
                )
            base_url = os.environ.get(
                "AGENTUITY_TRANSPORT_URL", "https://api.agentuity.com"
            )

            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            inject(headers)

            payload = {
                "chatId": chat_id,
                "message": reply,
                "reply_to_message_id": message_id,
                "agentId": agent_id,
                "parseMode": options.get("parseMode"),
            }

            # Remove None values from payload
            payload = {k: v for k, v in payload.items() if v is not None}

            url = f"{base_url}/telegram/{agent_id}/reply"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    raise ValueError(
                        f"Error sending telegram reply: {response.text} ({response.status_code})"
                    ) 