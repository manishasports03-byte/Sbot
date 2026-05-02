"""Coordinated access-runtime service for modular membership enforcement."""

from __future__ import annotations

import discord


class AccessRuntimeService:
    def __init__(self, memberships, permission_roles, access_engine):
        self.memberships = memberships
        self.permission_roles = permission_roles
        self.access = access_engine

    async def plan_member_sync(self, member) -> dict[str, object]:
        membership_plan = await self.memberships.sync_member_roles(member)
        base_role_plan = await self.memberships.sync_base_role(member)
        permission_role_plan = await self.permission_roles.plan_role_sync(member)

        membership_config = (await self.memberships.guild_config_service.get_guild_config(member.guild.id)).membership
        verified_bonus_add: list[int] = []
        if (
            membership_config.verified_role_id
            and membership_config.verified_bonus_role_id
            and self.access.member_has_role(member, membership_config.verified_role_id)
            and not self.access.member_has_role(member, membership_config.verified_bonus_role_id)
        ):
            verified_bonus_add.append(membership_config.verified_bonus_role_id)

        combined_add = sorted(
            {
                *membership_plan["add"],
                *base_role_plan["add"],
                *permission_role_plan["add"],
                *verified_bonus_add,
            }
        )
        combined_remove = sorted(
            {
                *membership_plan["remove"],
                *base_role_plan["remove"],
                *permission_role_plan["remove"],
            }
        )

        return {
            "membership": membership_plan,
            "base_role": base_role_plan,
            "permission_roles": permission_role_plan,
            "verified_bonus": {"add": verified_bonus_add, "remove": []},
            "combined": {
                "add": combined_add,
                "remove": combined_remove,
            },
        }

    async def apply_member_sync(self, member, dry_run: bool = False) -> dict[str, object]:
        plan = await self.plan_member_sync(member)
        if dry_run:
            return plan

        add_ids = plan["combined"]["add"]
        remove_ids = plan["combined"]["remove"]
        roles_to_add = [member.guild.get_role(role_id) for role_id in add_ids]
        roles_to_remove = [member.guild.get_role(role_id) for role_id in remove_ids]
        roles_to_add = [role for role in roles_to_add if role is not None and role not in member.roles]
        roles_to_remove = [role for role in roles_to_remove if role is not None and role in member.roles]

        if roles_to_add:
            await member.add_roles(*roles_to_add, reason="Modular access runtime sync")
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Modular access runtime sync")
        return plan

    async def plan_guild_access(self, guild) -> dict[int, dict[int, discord.PermissionOverwrite]]:
        return await self.memberships.compute_channel_access(guild)

    async def diff_guild_access(self, guild) -> list[dict[str, object]]:
        plans = await self.plan_guild_access(guild)
        diffs: list[dict[str, object]] = []

        for channel_id, role_overwrites in plans.items():
            channel = guild.get_channel(channel_id)
            if channel is None:
                diffs.append(
                    {
                        "type": "missing_channel",
                        "channel_id": channel_id,
                    }
                )
                continue

            for role_id, expected_overwrite in role_overwrites.items():
                role = guild.get_role(role_id)
                if role is None:
                    diffs.append(
                        {
                            "type": "missing_role",
                            "channel_id": channel_id,
                            "role_id": role_id,
                        }
                    )
                    continue

                actual_overwrite = channel.overwrites_for(role)
                expected_pairs = self.normalize_overwrite(expected_overwrite)
                actual_pairs = self.normalize_overwrite(actual_overwrite)
                if expected_pairs != actual_pairs:
                    diffs.append(
                        {
                            "type": "overwrite_mismatch",
                            "channel_id": channel_id,
                            "role_id": role_id,
                            "expected": expected_pairs,
                            "actual": actual_pairs,
                        }
                    )

        return diffs

    @staticmethod
    def normalize_overwrite(overwrite: discord.PermissionOverwrite) -> dict[str, int]:
        allow, deny = overwrite.pair()
        return {
            "allow": allow.value,
            "deny": deny.value,
        }
