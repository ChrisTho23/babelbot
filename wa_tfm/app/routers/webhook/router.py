from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from ....client import MCPClient
from ...dependencies import get_client
from .models import WebhookResponse, WhatsAppMessage

router = APIRouter(
    prefix="/webhook",
    tags=["webhook"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=WebhookResponse)
async def webhook_handler(
    message: WhatsAppMessage,
    client: Annotated[MCPClient, Depends(get_client)]
):
    try:
        # Here you can process the message as needed
        # For example, log it, store it, or trigger other actions
        
        print(f"Received message:")
        print(f"From: {message.sender}")
        print(f"Content: {message.content}")
        print(f"Time: {message.timestamp}")
        print(f"Chat JID: {message.chat_jid}")
        if message.media_type:
            print(f"Media Type: {message.media_type}")

        response = await client.process_query(
            message=message
        )
        print(f"Claude's response: {response}")
        
        return WebhookResponse(
            status="success",
            message="Message processed successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )
    
@router.get("/health")
async def health_check():
    return {"status": "healthy"}