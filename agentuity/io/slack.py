import json
import os
import httpx
from typing import Optional, Dict, Union, Any
from dataclasses import dataclass, asdict
from opentelemetry import trace
from opentelemetry.propagate import inject
from agentuity import __version__
from agentuity.server.types import (
    AgentRequestInterface,
    AgentContextInterface,
    SlackMessageInterface,
)


@dataclass
class SlackReplyPayload:
    """
    Payload structure for Slack reply requests.
    """
    agentId: str
    channel: str
    text: Optional[str] = None
    blocks: Optional[str] = None
    thread_ts: Optional[str] = None


class SlackEventData:
    """
    Represents the inner event data for Slack events.
    """
    def __init__(self, data: Dict[str, Any]):
        self.type: str = data.get("type", "")
        self.channel: str = data.get("channel", "")
        self.user: str = data.get("user", "")
        self.text: str = data.get("text", "")
        self.ts: str = data.get("ts", "")
        self.event_ts: str = data.get("event_ts", "")
        self.channel_type: str = data.get("channel_type", "")
        self.thread_ts: Optional[str] = data.get("thread_ts")


class SlackEventPayload:
    """
    Represents a Slack event webhook payload.
    """
    def __init__(self, data: Dict[str, Any]):
        self.token: str = data.get("token", "")
        self.challenge: str = data.get("challenge", "")
        self.type: str = data.get("type", "")
        self.team_id: str = data.get("team_id", "")
        self.api_app_id: str = data.get("api_app_id", "")
        self.event: Optional[SlackEventData] = None
        
        if "event" in data and data["event"]:
            self.event = SlackEventData(data["event"])


class SlackMessagePayload:
    """
    Represents a Slack slash command payload.
    """
    def __init__(self, data: Dict[str, Any]):
        self.token: str = data.get("token", "")
        self.team_id: str = data.get("team_id", "")
        self.team_domain: str = data.get("team_domain", "")
        self.channel_id: str = data.get("channel_id", "")
        self.channel_name: str = data.get("channel_name", "")
        self.user_id: str = data.get("user_id", "")
        self.user_name: str = data.get("user_name", "")
        self.command: str = data.get("command", "")
        self.text: str = data.get("text", "")
        self.response_url: str = data.get("response_url", "")
        self.trigger_id: str = data.get("trigger_id", "")
        self.ts: str = data.get("ts", "")
        self.thread_ts: Optional[str] = data.get("thread_ts")
        self.event_ts: Optional[str] = data.get("event_ts")


class Slack(SlackMessageInterface):
    """
    A class representing a Slack message with the common information so processing can be done on it.
    """
    
    def __init__(self, data: Union[SlackEventPayload, SlackMessagePayload], message_type: str):
        """
        Initialize a Slack object.
        
        Args:
            data: The Slack event or message payload.
            message_type: The type of message ('slack-event' or 'slack-message').
        """
        self._message_type = message_type
        self._payload = data
        
        if message_type == 'slack-event':
            self._event_payload = data if isinstance(data, SlackEventPayload) else None
            self._message_payload = None
        else:
            self._event_payload = None
            self._message_payload = data if isinstance(data, SlackMessagePayload) else None

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return json.dumps({
            "message_type": self._message_type,
            "team_id": self.team_id,
            "channel": self.channel,
            "user": self.user,
            "text": self.text
        })

    @property
    def message_type(self) -> str:
        return self._message_type

    @property
    def token(self) -> str:
        return getattr(self._payload, "token", "")

    @property
    def team_id(self) -> str:
        return getattr(self._payload, "team_id", "")

    @property
    def challenge(self) -> Optional[str]:
        return getattr(self._event_payload, "challenge", None) if self._event_payload else None

    @property
    def event_type(self) -> Optional[str]:
        return getattr(self._event_payload, "type", None) if self._event_payload else None

    @property
    def event(self) -> Optional[SlackEventData]:
        return getattr(self._event_payload, "event", None) if self._event_payload else None

    @property
    def channel_id(self) -> Optional[str]:
        return getattr(self._message_payload, "channel_id", None) if self._message_payload else None

    @property
    def channel_name(self) -> Optional[str]:
        return getattr(self._message_payload, "channel_name", None) if self._message_payload else None

    @property
    def user_id(self) -> Optional[str]:
        return getattr(self._message_payload, "user_id", None) if self._message_payload else None

    @property
    def user_name(self) -> Optional[str]:
        return getattr(self._message_payload, "user_name", None) if self._message_payload else None

    @property
    def command(self) -> Optional[str]:
        return getattr(self._message_payload, "command", None) if self._message_payload else None

    @property
    def response_url(self) -> Optional[str]:
        return getattr(self._message_payload, "response_url", None) if self._message_payload else None

    @property
    def trigger_id(self) -> Optional[str]:
        return getattr(self._message_payload, "trigger_id", None) if self._message_payload else None

    @property
    def thread_ts(self) -> Optional[str]:
        if self._event_payload and self._event_payload.event:
            return getattr(self._event_payload.event, "thread_ts", None)
        return None

    @property
    def event_ts(self) -> Optional[str]:
        if self._event_payload and self._event_payload.event:
            return getattr(self._event_payload.event, "event_ts", None)
        return None

    @property
    def ts(self) -> Optional[str]:
        if self._event_payload and self._event_payload.event:
            return getattr(self._event_payload.event, "ts", None)
        return None

    @property
    def text(self) -> str:
        if self._event_payload and self._event_payload.event:
            return getattr(self._event_payload.event, "text", "")
        if self._message_payload:
            return getattr(self._message_payload, "text", "")
        return ""

    @property
    def user(self) -> str:
        if self._event_payload and self._event_payload.event:
            return getattr(self._event_payload.event, "user", "")
        if self._message_payload:
            return getattr(self._message_payload, "user_id", "")
        return ""

    @property
    def channel(self) -> str:
        if self._event_payload and self._event_payload.event:
            return getattr(self._event_payload.event, "channel", "")
        if self._message_payload:
            return getattr(self._message_payload, "channel_id", "")
        return ""

    def _extract_auth_token(self, req: AgentRequestInterface) -> str:
        """
        Extract slack authorization token from request metadata.
        
        Args:
            req: The agent request containing metadata.
            
        Returns:
            The slack authorization token.
            
        Raises:
            ValueError: If the auth token is not found in metadata.
        """
        if hasattr(req, "metadata") and isinstance(req.metadata, dict):
            auth_token = req.metadata.get("slack-auth-token")
            if auth_token:
                return auth_token
        
        raise ValueError(
            "slack authorization token is required but not found in metadata"
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

    def _get_tracer(self):
        """
        Get the OpenTelemetry tracer for slack operations.
        
        Returns:
            The tracer instance.
        """
        return trace.get_tracer("slack")

    def _build_request_headers(self, api_key: str, auth_token: str) -> dict:
        """
        Build HTTP headers for the slack reply request.
        
        Args:
            api_key: The API key for authorization.
            auth_token: The slack authorization token.
            
        Returns:
            Dictionary containing the request headers.
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Slack-Auth-Token": auth_token,
            "User-Agent": f"Agentuity Python SDK/{__version__}",
            "Content-Type": "application/json",
            "X-Agentuity-Slack-Team-Id": self.team_id,
        }
        inject(headers)
        return headers

    def _build_payload(self, ctx: AgentContextInterface, options: dict) -> dict:
        """
        Build the request payload for the slack reply.
        
        Args:
            ctx: The agent context.
            options: The options dictionary containing reply data.
            
        Returns:
            Dictionary containing the request payload with None values removed.
        """
        thread_ts = options.get("thread_ts")
        in_thread = options.get("in_thread", thread_ts is not None)
        
        payload = asdict(SlackReplyPayload(
            agentId=ctx.agentId,
            channel=self.channel,
            text=options.get("text"),
            blocks=options.get("blocks"),
            thread_ts=thread_ts if in_thread else None,
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
        Make the HTTP API request to send the slack reply.
        
        Args:
            base_url: The base URL for the API.
            headers: The request headers.
            payload: The request payload.
            
        Raises:
            ValueError: If the API request fails.
        """
        url = f"{base_url}/slack/reply"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise ValueError(
                    f"error sending slack reply: {response.text} ({response.status_code})"
                )

    async def send_reply(
        self,
        req: AgentRequestInterface,
        ctx: AgentContextInterface,
        reply: Union[str, dict],
        options: dict = {}
    ) -> None:
        """
        Send a reply to this Slack message.
        
        Args:
            req: The triggering agent request, used to extract metadata such as slack-auth-token.
            ctx: The agent context, used to get the base_url and agentId.
            reply: The text body of the reply or a dictionary with text and blocks.
            options: Optional parameters including in_thread (boolean) and thread_ts (string).
        """
        if options is None:
            options = {}
            
        if isinstance(reply, str):
            options["text"] = reply
        elif isinstance(reply, dict):
            options.update(reply)
            
        # Extract authentication token
        auth_token = self._extract_auth_token(req)
        
        # Get API configuration
        api_key, base_url = self._get_api_configuration()
        
        # Set up tracing
        tracer = self._get_tracer()
        
        with tracer.start_as_current_span("agentuity.slack.reply") as span:
            span.set_attribute("@agentuity/agentId", ctx.agentId)
            span.set_attribute("@agentuity/slackTeamId", self.team_id)
            span.set_attribute("@agentuity/slackMessageType", self.message_type)
            
            if self.channel:
                span.set_attribute("@agentuity/slackChannel", self.channel)
            
            try:
                # Build request components
                headers = self._build_request_headers(api_key, auth_token)
                payload = self._build_payload(ctx, options)
                
                # Make the API request
                await self._make_api_request(base_url, headers, payload)
                
                # Set successful status
                span.set_status(trace.Status(trace.StatusCode.OK))
                
            except Exception as e:
                # Set error status
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise


async def parse_slack(data: bytes, message_type: str = 'slack-event') -> Slack:
    """
    Parse a slack message from bytes and return a Slack object.
    
    Args:
        data: The raw bytes data containing the Slack message.
        message_type: The type of message ('slack-event' or 'slack-message').
        
    Returns:
        A Slack object representing the parsed message.
        
    Raises:
        ValueError: If the data cannot be parsed as a valid Slack message.
    """
    try:
        msg_data = json.loads(data.decode('utf-8'))
        
        if message_type == 'slack-event':
            payload = SlackEventPayload(msg_data)
            if not payload.token or not payload.type or not payload.team_id:
                raise ValueError("Invalid Slack event: missing required fields")
        else:
            payload = SlackMessagePayload(msg_data)
            if not payload.token or not payload.team_id or not payload.channel_id or not payload.user_id:
                raise ValueError("Invalid Slack message: missing required fields")
                
        return Slack(payload, message_type)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(
            f"Failed to parse slack message: {str(error)}"
        )
