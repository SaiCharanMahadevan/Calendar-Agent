from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr

class Email(BaseModel):
    """Email model for storing email information."""
    id: str
    subject: str
    sender: EmailStr
    recipient: EmailStr
    content: str
    timestamp: datetime
    is_read: bool = False
    attachments: List[str] = []

class EmailSummary(BaseModel):
    """Model for email summaries."""
    total_emails: int
    unread_count: int
    recent_emails: List[Email]
    summary: str

class CalendarEvent(BaseModel):
    """Model for calendar events."""
    id: str
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    attendees: List[EmailStr] = []

class Message(BaseModel):
    """Model for chat messages."""
    role: str
    content: str
    timestamp: datetime = datetime.now()

class ConversationHistory(BaseModel):
    """Model for managing conversation history."""
    messages: List[Message] = []
    max_history: int = 10

    def add_message(self, role: str, content: str) -> None:
        """Add a new message to the conversation history."""
        self.messages.append(Message(role=role, content=content))
        if len(self.messages) > self.max_history:
            self.messages.pop(0) 