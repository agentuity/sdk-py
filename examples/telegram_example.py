"""
Example usage of the Agentuity Telegram functionality.

This example shows how to:
1. Parse a Telegram message from raw data
2. Access message properties
3. Send a reply to a Telegram message
4. Send a typing indicator
"""

import asyncio
import json
from agentuity.io.telegram import Telegram, parse_telegram
from agentuity.server.types import AgentRequestInterface, AgentContextInterface


class MockAgentRequest:
    """Mock implementation of AgentRequestInterface for demonstration."""
    
    def __init__(self, metadata: dict):
        self.metadata = metadata


class MockAgentContext:
    """Mock implementation of AgentContextInterface for demonstration."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id


async def telegram_example():
    """Example of using the Telegram functionality."""
    
    # Example Telegram message data (this would come from Telegram webhook)
    telegram_message_data = {
        "message_id": 12345,
        "chat": {
            "id": 67890,
            "type": "private",
            "title": "Test Chat",
            "username": "test_user"
        },
        "from": {
            "id": 11111,
            "is_bot": False,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe"
        },
        "text": "Hello, Agentuity!",
        "date": 1640995200
    }
    
    # Convert to bytes (simulating raw webhook data)
    raw_data = json.dumps(telegram_message_data).encode('utf-8')
    
    print("=== Telegram Message Parsing Example ===")
    
    # Parse the Telegram message
    telegram_message = await parse_telegram(raw_data)
    
    print(f"Message ID: {telegram_message.message_id}")
    print(f"Chat ID: {telegram_message.chat_id}")
    print(f"Chat Type: {telegram_message.chat_type}")
    print(f"From User ID: {telegram_message.from_id}")
    print(f"From Username: {telegram_message.from_username}")
    print(f"From Name: {telegram_message.from_first_name} {telegram_message.from_last_name}")
    print(f"Message Text: {telegram_message.text}")
    print(f"Message Date: {telegram_message.date}")
    
    print("\n=== Message Properties ===")
    print(f"String representation: {telegram_message}")
    
    print("\n=== Reply Example ===")
    print("Note: The following would require actual API credentials and network access")
    
    # Create mock request and context (in real usage, these would be provided by the framework)
    mock_request = MockAgentRequest({
        "telegram-auth-token": "your_telegram_auth_token_here"
    })
    mock_context = MockAgentContext("your_agent_id_here")
    
    # Example of sending a reply (commented out to avoid actual API calls)
    # try:
    #     await telegram_message.send_reply(
    #         mock_request, 
    #         mock_context, 
    #         "Hello! I received your message.",
    #         options={"parseMode": "MarkdownV2"}
    #     )
    #     print("Reply sent successfully!")
    # except Exception as e:
    #     print(f"Error sending reply: {e}")
    
    # Example of sending typing indicator (commented out to avoid actual API calls)
    # try:
    #     await telegram_message.send_typing(mock_request, mock_context)
    #     print("Typing indicator sent!")
    # except Exception as e:
    #     print(f"Error sending typing indicator: {e}")
    
    print("Example completed!")


if __name__ == "__main__":
    asyncio.run(telegram_example()) 