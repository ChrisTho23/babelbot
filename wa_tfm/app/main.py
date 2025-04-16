import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from .routers import root_router, webhook_router
from .whatsapp import WhatsAppClient
from .db import DBClient

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = await DBClient.initialize(
        url=os.getenv("SUPABASE_URL"), key=os.getenv("SUPABASE_KEY")
    )
    client = await WhatsAppClient.get_instance(db)
    await client.connect_to_server()

    yield

    # Cleanup on shutdown
    await client.cleanup()


app = FastAPI(
    title="WhatsApp Message Handler",
    description="API for handling WhatsApp messages and webhooks",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(webhook_router)
app.include_router(root_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
