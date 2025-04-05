import asyncio

from fire import Fire

from wa_tfm import MCPClient


async def main(server_script_path: str):
    client = MCPClient()
    try:
        await client.connect_to_server(server_script_path)
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    Fire(main)