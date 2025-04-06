from fastapi import FastAPI
from .routers import webhook_router, root_router
from ..client import MCPClient
from contextlib import asynccontextmanager
import uvicorn

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the client on startup
    client = await MCPClient.get_instance()
    await client.connect_to_server("wa_tfm/whatsapp-mcp/whatsapp-mcp-server/main.py")
    
    yield
    
    # Cleanup on shutdown
    await client.cleanup()

app = FastAPI(
    title="WhatsApp Message Handler",
    description="API for handling WhatsApp messages and webhooks",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(webhook_router)
app.include_router(root_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)