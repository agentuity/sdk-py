import pytest
import json
from unittest.mock import Mock, patch
from agentuity.io.telegram import Telegram, TelegramReply, parse_telegram, TelegramResponse


class TestTelegramResponse:
    """Test suite for TelegramResponse class."""

    def test_telegram_response_initialization(self):
        """Test initialization of TelegramResponse."""
        data = {
            "message_id": 123,
            "chat": {"id": 456, "type": "private"},
            "from": {"id": 789, "first_name": "John", "username": "john_doe"},
            "text": "Hello, world!",
            "date": 1640995200
        }
        
        response = TelegramResponse(data)
        
        assert response.message_id == 123
        assert response.chat == {"id": 456, "type": "private"}
        assert response.from_user == {"id": 789, "first_name": "John", "username": "john_doe"}
        assert response.text == "Hello, world!"
        assert response.date == 1640995200


class TestTelegramReply:
    """Test suite for TelegramReply class."""

    def test_telegram_reply_initialization(self):
        """Test initialization of TelegramReply."""
        reply = TelegramReply("Test reply")
        assert reply.text == "Test reply"


class TestTelegram:
    """Test suite for Telegram class."""

    def setup_method(self):
        """Set up test data."""
        self.telegram_data = {
            "message_id": 123,
            "chat": {
                "id": 456,
                "type": "private",
                "title": "Test Chat",
                "username": "test_chat"
            },
            "from": {
                "id": 789,
                "is_bot": False,
                "first_name": "John",
                "last_name": "Doe",
                "username": "john_doe"
            },
            "text": "Hello, world!",
            "date": 1640995200
        }
        self.telegram_response = TelegramResponse(self.telegram_data)
        self.telegram = Telegram(self.telegram_response)

    def test_telegram_initialization(self):
        """Test initialization of Telegram."""
        assert self.telegram._message == self.telegram_response

    def test_telegram_properties(self):
        """Test Telegram properties."""
        assert self.telegram.message_id == 123
        assert self.telegram.chat_id == 456
        assert self.telegram.chat_type == "private"
        assert self.telegram.from_id == 789
        assert self.telegram.from_username == "john_doe"
        assert self.telegram.from_first_name == "John"
        assert self.telegram.from_last_name == "Doe"
        assert self.telegram.text == "Hello, world!"
        assert self.telegram.date == 1640995200

    def test_telegram_string_representation(self):
        """Test string representation of Telegram."""
        repr_str = self.telegram.__repr__()
        assert "message_id" in repr_str
        assert "123" in repr_str
        assert "Hello, world!" in repr_str

    def test_telegram_str_method(self):
        """Test str method of Telegram."""
        str_result = str(self.telegram)
        assert str_result == self.telegram.__repr__()

    @pytest.mark.asyncio
    async def test_send_reply(self):
        """Test send_reply method."""
        mock_request = Mock()
        mock_request.metadata = {"telegram-auth-token": "test_token"}
        
        mock_context = Mock()
        mock_context.agent_id = "test_agent"
        
        with patch('agentuity.io.telegram.httpx.AsyncClient') as mock_client, \
             patch.dict('os.environ', {'AGENTUITY_API_KEY': 'test_api_key'}):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            await self.telegram.send_reply(mock_request, mock_context, "Test reply")
            
            # Verify the API call was made
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_typing(self):
        """Test send_typing method."""
        mock_request = Mock()
        mock_request.metadata = {"telegram-auth-token": "test_token"}
        
        mock_context = Mock()
        mock_context.agent_id = "test_agent"
        
        with patch('agentuity.io.telegram.httpx.AsyncClient') as mock_client, \
             patch.dict('os.environ', {'AGENTUITY_API_KEY': 'test_api_key'}):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            await self.telegram.send_typing(mock_request, mock_context)
            
            # Verify the API call was made
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_reply_missing_auth_token(self):
        """Test send_reply with missing auth token."""
        mock_request = Mock()
        mock_request.metadata = {}
        
        mock_context = Mock()
        mock_context.agent_id = "test_agent"
        
        with pytest.raises(ValueError, match="telegram authorization token is required"):
            await self.telegram.send_reply(mock_request, mock_context, "Test reply")


class TestParseTelegram:
    """Test suite for parse_telegram function."""

    @pytest.mark.asyncio
    async def test_parse_telegram_success(self):
        """Test successful parsing of telegram data."""
        telegram_data = {
            "message_id": 123,
            "chat": {"id": 456, "type": "private"},
            "from": {"id": 789, "first_name": "John"},
            "text": "Hello, world!",
            "date": 1640995200
        }
        
        data_bytes = json.dumps(telegram_data).encode('utf-8')
        
        result = await parse_telegram(data_bytes)
        
        assert isinstance(result, Telegram)
        assert result.message_id == 123
        assert result.text == "Hello, world!"

    @pytest.mark.asyncio
    async def test_parse_telegram_invalid_json(self):
        """Test parsing with invalid JSON."""
        invalid_data = b"invalid json data"
        
        with pytest.raises(ValueError, match="Failed to parse telegram message"):
            await parse_telegram(invalid_data)

    @pytest.mark.asyncio
    async def test_parse_telegram_invalid_encoding(self):
        """Test parsing with invalid encoding."""
        # Create bytes that can't be decoded as UTF-8
        invalid_data = b'\xff\xfe\xfd'
        
        with pytest.raises(ValueError, match="Failed to parse telegram message"):
            await parse_telegram(invalid_data) 