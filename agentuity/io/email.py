import re
import os
import mailparser
from email.utils import formataddr
from opentelemetry.propagate import inject
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from typing import List
from agentuity import __version__
import httpx
from opentelemetry import trace
from agentuity.server.util import deprecated
from agentuity.server.types import (
    AgentRequestInterface,
    AgentContextInterface,
    EmailInterface,
    EmailAttachmentInterface,
    OutgoingEmailAttachmentInterface,
)


class EmailAttachment(OutgoingEmailAttachmentInterface):
    """
    Represents an outgoing email attachment with streaming data support.
    """

    from agentuity.server.data import DataLike

    def __init__(
        self,
        filename: str,
        data: "DataLike",
        content_type: str | None = None,
    ):
        self._filename = filename
        from agentuity.server.data import dataLikeToData

        self._data = dataLikeToData(data, content_type)

    def data(self):
        return self._data

    @property
    def filename(self):
        return self._filename

    def __repr__(self):
        return f"EmailAttachment(filename={self.filename})"


class IncomingEmailAttachment(EmailAttachmentInterface):
    """
    Represents an email attachment with streaming data support.
    """

    def __init__(self, attachment: dict):
        self._filename = attachment.get("filename")
        cd = attachment.get("content-disposition")
        self._content_disposition = re.split(r";\s*", cd)[0].strip()
        self._url = self._parse_url_from_content_disposition(cd)

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def content_disposition(self) -> str:
        return self._content_disposition

    def _parse_url_from_content_disposition(
        self, content_disposition: str | None
    ) -> str | None:
        """
        Parse the content_disposition header for a url property.
        """
        if not content_disposition:
            raise ValueError("content-disposition is required")

        match = re.search(r'url="([^"]+)"', content_disposition)
        if match:
            url = match.group(1)
            return url

        raise ValueError(
            f"Failed to parse url from content-disposition: {content_disposition}"
        )

    async def data(self):
        """
        Return a Data object that streams the attachment data asynchronously.
        """
        tracer = trace.get_tracer("email")
        with tracer.start_as_current_span("agentuity.email.attachment"):
            api_key = os.environ.get("AGENTUITY_SDK_KEY") or os.environ.get(
                "AGENTUITY_API_KEY"
            )
            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
            }
            inject(headers)
            async with httpx.AsyncClient() as client:
                response = await client.get(self._url, headers=headers)
                match response.status_code:
                    case 200:
                        content_type = response.headers.get(
                            "Content-Type", "application/octet-stream"
                        )
                        import asyncio
                        from agentuity.server.data import Data

                        reader = asyncio.StreamReader()
                        reader.feed_data(response.content)
                        reader.feed_eof()
                        return Data(content_type, reader)
                    case 404:
                        raise ValueError(f"Attachment not found: {self._url}")
                    case _:
                        raise ValueError(f"Failed to get attachment: {self._url}")

    def __repr__(self):
        return f"IncomingEmailAttachment(filename={self.filename})"


class Email(EmailInterface):
    """
    A class representing an email.
    """

    def __init__(self, email: str):
        """
        Initialize an Email object.
        """
        try:
            self._email = mailparser.parse_from_string(email)
        except Exception as e:
            # Initialize with empty email object or re-raise with more context
            raise ValueError(f"Failed to parse email: {str(e)}") from e

    def __str__(self) -> str:
        """
        Return a string representation of the email.
        """
        return self.__repr__()

    def __repr__(self) -> str:
        """
        Return a string representation of the email.
        """
        return (
            f"Email(id={self.messageId},from={self.from_email},subject={self.subject})"
        )

    @property
    def subject(self) -> str | None:
        """
        Return the subject of the email.
        """
        return getattr(self._email, "subject", None)

    @property
    def from_email(self) -> str | None:
        """
        Return the from email address of the email.
        """
        if not hasattr(self._email, "from_") or not self._email.from_:
            return None
        if isinstance(self._email.from_, list) and len(self._email.from_) > 0:
            if isinstance(self._email.from_[0], tuple):
                # ('Jeff Haynie', 'jhaynie@agentuity.com')
                return self._email.from_[0][1]
            else:
                return self._email.from_[0]
        elif isinstance(self._email.from_, str):
            return self._email.from_
        return None

    @property
    def from_name(self) -> str | None:
        """
        Return the from name of the email.
        """
        if not hasattr(self._email, "from_") or not self._email.from_:
            return None
        if isinstance(self._email.from_, list) and len(self._email.from_) > 0:
            if isinstance(self._email.from_[0], tuple):
                # ('Jeff Haynie', 'jhaynie@agentuity.com')
                return self._email.from_[0][0]
            elif isinstance(self._email.from_[0], str):
                return self._email.from_[0]
        elif isinstance(self._email.from_, str):
            return self._email.from_
        return None

    @property
    def to(self) -> str | None:
        """
        Return the to address of the email.
        """
        if not hasattr(self._email, "to") or not self._email.to:
            return None
        if isinstance(self._email.to, list) and len(self._email.to) > 0:
            if isinstance(self._email.to[0], tuple):
                # ('Jeff Haynie', 'jhaynie@agentuity.com')
                return self._email.to[0][1]
            elif isinstance(self._email.to[0], str):
                return self._email.to[0]
        elif isinstance(self._email.to, str):
            return self._email.to
        return None

    @property
    def to_name(self) -> str | None:
        """
        Return the to name of the email.
        """
        if not hasattr(self._email, "to") or not self._email.to:
            return None
        if isinstance(self._email.to, list) and len(self._email.to) > 0:
            if isinstance(self._email.to[0], tuple):
                # ('Jeff Haynie', 'jhaynie@agentuity.com')
                return self._email.to[0][0]
        return None

    @property
    def date(self) -> datetime | None:
        """
        Return the date of the email.
        """
        return getattr(self._email, "date", None)

    @deprecated("Use message_id instead")
    @property
    def messageId(self) -> str:
        """
        Return the message id of the email.
        """
        return getattr(self._email, "message_id", "")

    @property
    def message_id(self) -> str:
        """
        Return the message id of the email.
        """
        return getattr(self._email, "message_id", "")

    @property
    def headers(self) -> dict[str, str]:
        """
        Return the headers of the email.
        """
        return getattr(self._email, "headers", {})

    @property
    def text(self) -> str:
        """
        Return the text of the email.
        """
        return "\n".join(getattr(self._email, "text_plain", ""))

    @property
    def html(self) -> str:
        """
        Return the html of the email.
        """
        return "\n".join(getattr(self._email, "text_html", ""))

    @property
    def attachments(self) -> List["IncomingEmailAttachment"]:
        """
        Return the attachments of the email as EmailAttachment objects.
        """
        raw_attachments = getattr(self._email, "attachments", [])
        return [IncomingEmailAttachment(a) for a in raw_attachments]

    async def sendReply(
        self,
        request: "AgentRequestInterface",
        context: "AgentContextInterface",
        subject: str = None,
        text: str = None,
        html: str = None,
        attachments: List["OutgoingEmailAttachmentInterface"] = None,
    ):
        """
        Send a reply to this email using the Agentuity email API.
        Args:
            request (AgentRequest): The triggering agent request, used to extract metadata such as email-auth-token.
            context (AgentContext): The agent context, used to get the base_url and agentId.
            to (str): Recipient email address. Defaults to the original sender if not provided.
            subject (str): Subject of the reply. Defaults to 'Re: <original subject>'.
            body (str): Plain text body of the reply.
            html (str): HTML body of the reply.
            attachments (list): List of file-like objects or dicts with 'filename' and 'content'.
        """
        tracer = trace.get_tracer("email")
        with tracer.start_as_current_span("agentuity.email.reply") as span:
            # Extract email-auth-token from AgentRequest metadata
            email_auth_token = None
            if hasattr(request, "metadata") and isinstance(request.metadata, dict):
                email_auth_token = request.metadata.get("email-auth-token")
            if not email_auth_token:
                raise ValueError(
                    "Missing required email-auth-token in AgentRequest metadata for email reply."
                )
            span.set_attribute("@agentuity/agentId", context.agent_id)
            span.set_attribute("@agentuity/emailMessageId", self.message_id)

            headers = {
                "Authorization": f"Bearer {email_auth_token}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
                "Content-Type": "message/rfc822",
                "X-Agentuity-Message-Id": self.message_id,
            }
            inject(headers)

            if not self.to or not self.from_email:
                raise ValueError("Missing To/From when constructing reply email")

            # Outer message for attachments
            outer = MIMEMultipart("mixed")
            outer["In-Reply-To"] = self.message_id
            outer["References"] = self.message_id
            outer["Subject"] = subject or f"Re: {self.subject}"
            outer["From"] = formataddr((self.to_name or context.agent.name, self.to))
            outer["To"] = formataddr((self.from_name, self.from_email))
            outer["Date"] = datetime.now().isoformat()

            # Alternative part for text and html
            alt = MIMEMultipart("alternative")
            if text:
                alt.attach(MIMEText(text, "plain"))
            if html:
                alt.attach(MIMEText(html, "html"))
            outer.attach(alt)

            # Add any attachments
            if attachments:
                for a in attachments:
                    data = a.data()
                    buffer = await data.binary()
                    part = MIMEApplication(buffer)
                    part.add_header("Content-Type", data.content_type)
                    part.add_header(
                        "Content-Disposition", "attachment", filename=a.filename
                    )
                    outer.attach(part)

            email_body = outer.as_bytes()
            url = f"{context.base_url}/email/2025-03-17/{context.agentId}/reply"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, content=email_body, headers=headers)
                response.raise_for_status()
                return None
