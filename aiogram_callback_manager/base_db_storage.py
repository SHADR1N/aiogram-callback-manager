import asyncio
import time
from typing import Optional

import aiosqlite
from aiosqlite import Connection


class CallbackDataStorage:
    async def save(self, data_hash: str, data_bytes: bytes, timestamp: float):
        raise NotImplementedError

    async def load(self, data_hash: str) -> Optional[bytes]:
        raise NotImplementedError

    async def clean_old(self, expiry_time: int):
        raise NotImplementedError
    async def init_db(self):
       raise NotImplementedError

class SQLiteStorage(CallbackDataStorage):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db_lock = asyncio.Lock()
        self.connection:Optional[Connection]=None

    async def clean_old(self, expiry_time: int):
        current_time = time.time()
        async with self._db_lock:
            await self.connection.execute(
                    "DELETE FROM callback_data WHERE ? - created_at > ?",
                    (current_time, expiry_time)
                )
            await self.connection.commit()


    async def init_db(self):
        self.connection = await aiosqlite.connect(self.db_path)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS callback_data (
                hash TEXT PRIMARY KEY,
                data BLOB,
                created_at REAL
            )
        """)
        await self.connection.commit()

    async def save(self, data_id: str, data_bytes: bytes, timestamp: float):
        async with self._db_lock:
            await self.connection.execute(
                "INSERT OR REPLACE INTO callback_data (hash, data, created_at) VALUES (?, ?, ?)",
                (data_id, data_bytes, timestamp)
            )
            await self.connection.commit()

    async def load(self, data_id: str) -> Optional[bytes]:
        async with self._db_lock:
            async with self.connection.execute(
                    "SELECT data FROM callback_data WHERE hash = ?",
                    (data_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
        return None

    async def close(self):
        await self.connection.close()
