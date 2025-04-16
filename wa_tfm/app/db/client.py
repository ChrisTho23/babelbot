from supabase import create_client, Client
from typing import Optional

class DBClient:
    _instance: Optional[Client] = None

    @classmethod
    async def initialize(cls, url: str, key: str) -> Client:
        if not cls._instance:
            cls._instance = create_client(url, key)
        return cls._instance

    @classmethod
    def get_instance(cls) -> Optional[Client]:
        return cls._instance