from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class WhatsAppMessage(BaseModel):
    timestamp: datetime
    sender: str
    content: str
    chat_jid: str
    is_from_me: bool
    media_type: Optional[str] = None
    message_id: str

# Define response model
class WebhookResponse(BaseModel):
    status: str
    message: str