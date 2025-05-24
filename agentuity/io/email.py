import mailparser
from datetime import datetime


class Email(dict):
    """
    A class representing an email.
    """

    def __init__(self, email: str):
        """
        Initialize an Email object.
        """
        try:
            self._email = mailparser.parse_from_string(email)
            super().__init__(self._get_email_dict())
        except Exception as e:
            # Initialize with empty email object or re-raise with more context
            raise ValueError(f"Failed to parse email: {str(e)}") from e

    def _get_email_dict(self) -> dict:
        """
        Get email data as a dictionary.
        """
        return {
            "subject": self.subject,
            "from_email": self.from_email,
            "from_name": self.from_name,
            "to": self.to,
            "date": self.date.isoformat() if self.date else None,
            "messageId": self.messageId,
            "headers": self.headers,
            "text": self.text,
            "html": self.html,
            "attachments": self.attachments,
        }

    def __iter__(self):
        """
        Make the Email object directly JSON serializable.
        """
        return iter(self._get_email_dict().items())

    def __getitem__(self, key):
        """
        Make the Email object behave like a dictionary.
        """
        email_dict = self._get_email_dict()
        if key not in email_dict:
            raise KeyError(key)
        return email_dict[key]

    def keys(self):
        """
        Return the keys of the email dictionary.
        """
        return [
            "subject",
            "from_email",
            "from_name",
            "to",
            "date",
            "messageId",
            "headers",
            "text",
            "html",
            "attachments",
        ]

    def to_dict(self) -> dict:
        """
        Convert the Email object to a dictionary.
        """
        return self._get_email_dict()

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
    def date(self) -> datetime | None:
        """
        Return the date of the email.
        """
        return getattr(self._email, "date", None)

    @property
    def messageId(self) -> str:
        """
        Return the message id of the email.
        """
        return getattr(self._email, "message_id", "")

    @property
    def headers(self) -> dict:
        """
        Return the headers of the email.
        """
        return getattr(self._email, "headers", {})

    @property
    def text(self) -> str:
        """
        Return the text of the email.
        """
        return getattr(self._email, "text_plain", "")

    @property
    def html(self) -> str:
        """
        Return the html of the email.
        """
        return getattr(self._email, "text_html", "")

    @property
    def attachments(self) -> list:
        """
        Return the attachments of the email.
        """
        return getattr(self._email, "attachments", [])
