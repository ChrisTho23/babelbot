from wa_tfm.client import MCPClient

async def get_client() -> MCPClient:
    return await MCPClient.get_instance()