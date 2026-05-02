"""Async database wrapper for the modular architecture."""

from __future__ import annotations

import asyncio

import asyncpg


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.pool is not None:
            return

        async with self._connect_lock:
            if self.pool is None:
                self.pool = await asyncpg.create_pool(self.database_url)

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def ensure_schema(self) -> None:
        await self.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_configs (
                guild_id BIGINT PRIMARY KEY,
                prefix TEXT DEFAULT '.',
                membership_json JSONB DEFAULT '{}'::jsonb,
                tickets_json JSONB DEFAULT '{}'::jsonb,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        await self.execute(
            """
            CREATE TABLE IF NOT EXISTS role_bindings (
                guild_id BIGINT,
                source_role_id BIGINT,
                target_role_id BIGINT,
                PRIMARY KEY (guild_id, source_role_id, target_role_id)
            )
            """
        )

    async def execute(self, query: str, *args):
        if self.pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        if self.pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        if self.pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        if self.pool is None:
            raise RuntimeError("Database pool is not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
