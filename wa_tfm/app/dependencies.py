from .whatsapp import MCPClient
from .db import DBClient


async def get_mcp_client() -> MCPClient:
    return await MCPClient.get_instance()


async def get_db_client() -> DBClient:
    return await DBClient.get_instance()
