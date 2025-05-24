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
        self._email = mailparser.parse_from_string(email)
        super().__init__(
            {
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
        )

    def __dict__(self):
        """
        Make the Email object directly JSON serializable.
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
        return iter(self.__dict__().items())

    def __getitem__(self, key):
        """
        Make the Email object behave like a dictionary.
        """
        if key == "subject":
            return self.subject
        elif key == "from_email":
            return self.from_email
        elif key == "from_name":
            return self.from_name
        elif key == "to":
            return self.to
        elif key == "date":
            return self.date.isoformat() if self.date else None
        elif key == "messageId":
            return self.messageId
        elif key == "headers":
            return self.headers
        elif key == "text":
            return self.text
        elif key == "html":
            return self.html
        elif key == "attachments":
            return self.attachments
        raise KeyError(key)

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
    def subject(self) -> str:
        """
        Return the subject of the email.
        """
        return self._email.subject

    @property
    def from_email(self) -> str | None:
        """
        Return the from email address of the email.
        """
        print(type(self._email.from_), self._email.from_)
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
        if isinstance(self._email.from_, list) and len(self._email.from_) > 0:
            if isinstance(self._email.from_[0], tuple):
                # ('Jeff Haynie', 'jhaynie@agentuity.com')
                return self._email.from_[0][0]
            else:
                return self._email.from_[0]
        return None

    @property
    def to(self) -> str:
        """
        Return the to address of the email.
        """
        if isinstance(self._email.to, list) and len(self._email.to) > 0:
            if isinstance(self._email.to[0], tuple):
                # ('Jeff Haynie', 'jhaynie@agentuity.com')
                return self._email.to[0][1]
            else:
                return self._email.to[0]
        return None

    @property
    def date(self) -> datetime | None:
        """
        Return the date of the email.
        """
        return self._email.date

    @property
    def messageId(self) -> str:
        """
        Return the message id of the email.
        """
        return self._email.message_id

    @property
    def headers(self) -> dict:
        """
        Return the headers of the email.
        """
        return self._email.headers

    @property
    def text(self) -> str:
        """
        Return the text of the email.
        """
        return self._email.text_plain

    @property
    def html(self) -> str:
        """
        Return the html of the email.
        """
        return self._email.text_html

    @property
    def attachments(self) -> list:
        """
        Return the attachments of the email.
        """
        return self._email.attachments
