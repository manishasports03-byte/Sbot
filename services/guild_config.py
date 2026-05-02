"""Guild-scoped configuration repository for modular services."""

from __future__ import annotations

import json

from core.defaults import build_default_guild_config, build_default_role_bindings
from core.models import GuildConfig, MembershipConfig, RoleBinding, TicketConfig


class GuildConfigService:
    def __init__(self, database):
        self.database = database

    async def ensure_schema(self) -> None:
        # Base schema is owned by core.database; this hook keeps the phase API stable.
        return

    async def get_guild_config(self, guild_id: int) -> GuildConfig:
        default_config = build_default_guild_config(guild_id)
        row = await self.database.fetchrow(
            """
            SELECT prefix, membership_json, tickets_json
            FROM guild_configs
            WHERE guild_id = $1
            """,
            guild_id,
        )
        if row is None:
            return default_config

        membership_payload = dict(row["membership_json"] or {})
        tickets_payload = dict(row["tickets_json"] or {})

        membership_merged = default_config.membership.to_payload()
        membership_merged.update(membership_payload)
        tickets_merged = default_config.tickets.to_payload()
        tickets_merged.update(tickets_payload)

        return GuildConfig(
            guild_id=guild_id,
            prefix=row["prefix"] or default_config.prefix,
            membership=MembershipConfig.from_payload(membership_merged),
            tickets=TicketConfig.from_payload(tickets_merged),
        )

    async def upsert_guild_config(self, config: GuildConfig) -> None:
        await self.database.execute(
            """
            INSERT INTO guild_configs (guild_id, prefix, membership_json, tickets_json, updated_at)
            VALUES ($1, $2, $3::jsonb, $4::jsonb, NOW())
            ON CONFLICT (guild_id)
            DO UPDATE SET
                prefix = EXCLUDED.prefix,
                membership_json = EXCLUDED.membership_json,
                tickets_json = EXCLUDED.tickets_json,
                updated_at = NOW()
            """,
            config.guild_id,
            config.prefix,
            json.dumps(config.membership.to_payload()),
            json.dumps(config.tickets.to_payload()),
        )

    async def get_role_bindings(self, guild_id: int) -> list[RoleBinding]:
        default_bindings = build_default_role_bindings()
        rows = await self.database.fetch(
            """
            SELECT source_role_id, target_role_id
            FROM role_bindings
            WHERE guild_id = $1
            ORDER BY target_role_id, source_role_id
            """,
            guild_id,
        )
        stored_bindings = [
            RoleBinding(source_role_id=row["source_role_id"], target_role_id=row["target_role_id"])
            for row in rows
        ]
        deduped = {
            (binding.source_role_id, binding.target_role_id): binding
            for binding in [*default_bindings, *stored_bindings]
        }
        return [
            deduped[key]
            for key in sorted(deduped, key=lambda pair: (pair[1], pair[0]))
        ]

    async def upsert_role_binding(self, guild_id: int, source_role_id: int, target_role_id: int) -> None:
        await self.database.execute(
            """
            INSERT INTO role_bindings (guild_id, source_role_id, target_role_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, source_role_id, target_role_id)
            DO NOTHING
            """,
            guild_id,
            source_role_id,
            target_role_id,
        )

    async def remove_role_binding(self, guild_id: int, source_role_id: int, target_role_id: int) -> None:
        await self.database.execute(
            """
            DELETE FROM role_bindings
            WHERE guild_id = $1 AND source_role_id = $2 AND target_role_id = $3
            """,
            guild_id,
            source_role_id,
            target_role_id,
        )
