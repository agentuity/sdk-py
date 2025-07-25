import json
import os
import httpx
from typing import Optional
from dataclasses import dataclass, asdict
from opentelemetry import trace
from opentelemetry.propagate import inject
from agentuity import __version__
from agentuity.server.types import (
    AgentRequestInterface,
    AgentContextInterface,
)


@dataclass
class TelegramReplyPayload:
    """
    Payload structure for Telegram reply requests.
    """
    chatId: int
    agentId: str
    message: Optional[str] = None
    action: Optional[str] = None
    parseMode: Optional[str] = None


class TelegramResponse:
    """
    Represents a Telegram message response structure.
    """
    def __init__(self, data: dict):
        self.message_id: int = data.get("message_id")
        self.chat = data.get("chat", {})
        self.from_user = data.get("from", {})
        self.text: str = data.get("text", "")
        self.date: int = data.get("date", 0)


class Telegram:
    """
    A class representing a telegram message with the common information so processing can be done on it.
    """
    
    def __init__(self, data: TelegramResponse):
        self._message = data

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return json.dumps({
            "message_id": self._message.message_id,
            "chat": self._message.chat,
            "from_user": self._message.from_user,
            "text": self._message.text,
            "date": self._message.date
        })

    @property
    def message_id(self) -> int:
        return self._message.message_id

    @property
    def chat_id(self) -> int:
        return self._message.chat.get("id")

    @property
    def chat_type(self) -> str:
        return self._message.chat.get("type", "")

    @property
    def from_id(self) -> int:
        return self._message.from_user.get("id")

    @property
    def from_username(self) -> Optional[str]:
        return self._message.from_user.get("username")

    @property
    def from_first_name(self) -> str:
        return self._message.from_user.get("first_name", "")

    @property
    def from_last_name(self) -> Optional[str]:
        return self._message.from_user.get("last_name")

    @property
    def text(self) -> str:
        return self._message.text

    @property
    def date(self) -> int:
        return self._message.date

    def _extract_auth_token(self, req: AgentRequestInterface) -> str:
        """
        Extract telegram authorization token from request metadata.
        
        Args:
            req: The agent request containing metadata.
            
        Returns:
            The telegram authorization token.
            
        Raises:
            ValueError: If the auth token is not found in metadata.
        """
        if hasattr(req, "metadata") and isinstance(req.metadata, dict):
            auth_token = req.metadata.get("telegram-auth-token")
            if auth_token:
                return auth_token
        
        raise ValueError(
            "telegram authorization token is required but not found in metadata"
        )

    def _get_api_configuration(self) -> tuple[str, str]:
        """
        Get API key and base URL from environment variables.
        
        Returns:
            Tuple of (api_key, base_url).
            
        Raises:
            ValueError: If the API key is not found in environment variables.
        """
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
        
        return api_key, base_url

    def _setup_tracing(self, ctx: AgentContextInterface) -> tuple:
        """
        Set up OpenTelemetry tracing for the telegram reply operation.
        
        Args:
            ctx: The agent context.
            
        Returns:
            Tuple of (tracer, span) for tracing.
        """
        tracer = trace.get_tracer("telegram")
        span = tracer.start_as_current_span("agentuity.telegram.reply")
        
        span.set_attribute("@agentuity/agentId", ctx.agent_id)
        span.set_attribute("@agentuity/telegramMessageId", self.message_id)
        span.set_attribute("@agentuity/telegramChatId", self.chat_id)
        
        return tracer, span

    def _build_request_headers(self, api_key: str) -> dict:
        """
        Build HTTP headers for the telegram reply request.
        
        Args:
            api_key: The API key for authorization.
            
        Returns:
            Dictionary containing the request headers.
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": f"Agentuity Python SDK/{__version__}",
            "Content-Type": "application/json",
            "X-Agentuity-Message-Id": str(self.message_id),
            "X-Agentuity-Chat-Id": str(self.chat_id),
        }
        inject(headers)
        return headers

    def _build_payload(self, ctx: AgentContextInterface, options: dict) -> dict:
        """
        Build the request payload for the telegram reply.
        
        Args:
            ctx: The agent context.
            options: The options dictionary containing reply data.
            
        Returns:
            Dictionary containing the request payload with None values removed.
        """
        payload = asdict(TelegramReplyPayload(
            chatId=self.chat_id,
            agentId=ctx.agent_id,
            message=options.get("reply"),
            action=options.get("action"),
            parseMode=options.get("parseMode"),
        ))
        
        # Remove None values from payload
        return {k: v for k, v in payload.items() if v is not None}

    async def _make_api_request(
        self, 
        base_url: str, 
        headers: dict, 
        payload: dict
    ) -> None:
        """
        Make the HTTP API request to send the telegram reply.
        
        Args:
            base_url: The base URL for the API.
            headers: The request headers.
            payload: The request payload.
            
        Raises:
            ValueError: If the API request fails.
        """
        url = f"{base_url}/telegram/reply"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise ValueError(
                    f"error sending telegram reply: {response.text} ({response.status_code})"
                )

    async def _send_reply(
        self,
        req: AgentRequestInterface,
        ctx: AgentContextInterface,
        options: dict = None
    ) -> None:
        """
        Internal method to send a reply to a Telegram message.
        """
        if options is None:
            options = {}
            
        # Extract authentication token
        auth_token = self._extract_auth_token(req)
        
        # Get API configuration
        api_key, base_url = self._get_api_configuration()
        
        # Set up tracing
        tracer, span = self._setup_tracing(ctx)
        
        try:
            # Build request components
            headers = self._build_request_headers(api_key)
            payload = self._build_payload(ctx, options)
            
            # Make the API request
            await self._make_api_request(base_url, headers, payload)
            
            # Set successful status
            span.set_status(trace.Status(trace.StatusCode.OK))
            
        except Exception as e:
            # Set error status
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise
        finally:
            span.end()

    async def send_reply(
        self,
        req: AgentRequestInterface,
        ctx: AgentContextInterface,
        reply: str,
        options: dict = None
    ) -> None:
        """
        Send a reply to this Telegram message.
        
        Args:
            req: The triggering agent request, used to extract metadata such as telegram-auth-token.
            ctx: The agent context, used to get the base_url and agentId.
            reply: The text body of the reply.
            options: Optional parameters including parseMode ('MarkdownV2' or 'HTML').
        """
        if options is None:
            options = {}
        return await self._send_reply(req, ctx, {"reply": reply, "parseMode": options.get("parseMode")})

    async def send_typing(
        self,
        req: AgentRequestInterface,
        ctx: AgentContextInterface,
    ) -> None:
        """
        Send a typing action to indicate the bot is typing.
        
        Args:
            req: The triggering agent request, used to extract metadata such as telegram-auth-token.
            ctx: The agent context, used to get the base_url and agentId.
        """
        return await self._send_reply(req, ctx, {"action": "typing"})


async def parse_telegram(data: bytes) -> Telegram:
    """
    Parse a telegram message from bytes and return a Telegram object.
    
    Args:
        data: The raw bytes data containing the Telegram message.
        
    Returns:
        A Telegram object representing the parsed message.
        
    Raises:
        ValueError: If the data cannot be parsed as a valid Telegram message.
    """
    try:
        msg_data = json.loads(data.decode('utf-8'))
        telegram_response = TelegramResponse(msg_data)
        return Telegram(telegram_response)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(
            f"Failed to parse telegram message: {str(error)}"
        )
