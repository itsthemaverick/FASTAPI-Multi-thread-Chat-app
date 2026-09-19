from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Enumeration of chat message types."""
    CHAT = "chat"
    SYSTEM = "system"
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"


class ChatMessage(BaseModel):
    """Data model representing a single chat message payload."""
    type: MessageType = MessageType.CHAT
    username: str
    content: str
    room: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now().strftime("%H:%M:%S")
    )


class RoomInfo(BaseModel):
    """Data model for room metadata."""
    name: str
    description: str
    active_users: int = 0
