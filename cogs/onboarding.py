"""Parallel onboarding and membership cog.

The live monolith remains authoritative until MODULAR_HANDLERS_ENABLED is set.
These handlers already use the extracted services so they can be validated
incrementally without deleting the old runtime.
"""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from core.logging import get_logger


class OnboardingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.container = bot.container  # type: ignore[attr-defined]
        self.logger = get_logger("sbot.cogs.onboarding")

    @property
    def modular_handlers_enabled(self) -> bool:
        return self.container.settings.modular_handlers_enabled

    @property
    def modular_shadow_mode(self) -> bool:
        return self.container.settings.modular_shadow_mode

    async def _apply_role_plan(self, member, plan: dict[str, list[int]], reason: str) -> None:
        add_ids = plan.get("add", [])
        remove_ids = plan.get("remove", [])

        roles_to_add = [member.guild.get_role(role_id) for role_id in add_ids]
        roles_to_remove = [member.guild.get_role(role_id) for role_id in remove_ids]
        roles_to_add = [role for role in roles_to_add if role is not None]
        roles_to_remove = [role for role in roles_to_remove if role is not None]

        if roles_to_add:
            await member.add_roles(*roles_to_add, reason=reason)
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=reason)

    async def _sync_member(self, member) -> None:
        if member.bot:
            return

        await self.container.access_runtime.apply_member_sync(
            member,
            dry_run=self.modular_shadow_mode,
        )

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.modular_handlers_enabled:
            return

        for guild in self.bot.guilds:
            if self.modular_shadow_mode:
                diffs = await self.container.access_runtime.diff_guild_access(guild)
                self.logger.info("access_shadow_scan", extra={"guild_id": guild.id, "diff_count": len(diffs)})
                continue

            plans = await self.container.access_runtime.plan_guild_access(guild)
            for channel_id, role_overwrites in plans.items():
                channel = guild.get_channel(channel_id)
                if channel is None:
                    continue
                for role_id, overwrite in role_overwrites.items():
                    role = guild.get_role(role_id)
                    if role is None:
                        continue
                    await channel.set_permissions(role, overwrite=overwrite)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not self.modular_handlers_enabled:
            return

        await self._sync_member(member)

        visibility_pings = await self.container.memberships.build_join_visibility_pings(member.guild)
        if not self.modular_shadow_mode:
            for payload in visibility_pings:
                channel = member.guild.get_channel(payload["channel_id"])
                if channel is None:
                    continue
                await channel.send(payload["content"], delete_after=payload["delete_after_seconds"])

        prompt = await self.container.memberships.build_join_prompt(member)
        channel = member.guild.get_channel(prompt["channel_id"]) if prompt["channel_id"] else None
        if channel is not None and not self.modular_shadow_mode:
            message = await channel.send(
                prompt["content"],
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
            await asyncio.sleep(int(prompt["delete_after_seconds"]))
            await message.delete()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if not self.modular_handlers_enabled or before.roles == after.roles:
            return
        await self._sync_member(after)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(OnboardingCog(bot))
