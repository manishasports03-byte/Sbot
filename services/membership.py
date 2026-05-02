"""Membership and onboarding service extracted from the monolith."""

from __future__ import annotations

import discord

from core.models import GuildConfig


class MembershipService:
    def __init__(self, guild_config_service, access_engine):
        self.guild_config_service = guild_config_service
        self.access = access_engine

    async def sync_member_roles(self, member, config: GuildConfig | None = None) -> dict[str, list[int]]:
        config = config or await self.guild_config_service.get_guild_config(member.guild.id)
        roles_to_add, roles_to_remove = self.access.plan_membership_role_sync(member, config)
        return {"add": roles_to_add, "remove": roles_to_remove}

    async def sync_base_role(self, member, config: GuildConfig | None = None) -> dict[str, list[int]]:
        config = config or await self.guild_config_service.get_guild_config(member.guild.id)
        roles_to_add, roles_to_remove = self.access.plan_base_role_sync(member, config)
        return {"add": roles_to_add, "remove": roles_to_remove}

    async def build_join_prompt(self, member, config: GuildConfig | None = None) -> dict[str, int | str | None]:
        config = config or await self.guild_config_service.get_guild_config(member.guild.id)
        membership = config.membership
        return {
            "channel_id": membership.verification_channel_id,
            "content": f"{member.mention} verify here",
            "delete_after_seconds": membership.join_verify_prompt_delete_seconds,
        }

    async def build_join_visibility_pings(self, guild, config: GuildConfig | None = None) -> list[dict[str, int | str]]:
        config = config or await self.guild_config_service.get_guild_config(guild.id)
        delete_after = config.membership.join_visibility_ping_delete_seconds
        payloads: list[dict[str, int | str]] = []
        for channel in guild.text_channels:
            me = guild.me
            if me is None:
                continue
            permissions = channel.permissions_for(me)
            if not permissions.view_channel or not permissions.send_messages:
                continue
            payloads.append(
                {
                    "channel_id": channel.id,
                    "content": ".",
                    "delete_after_seconds": delete_after,
                }
            )
        return payloads

    async def compute_channel_access(self, guild) -> dict[int, dict[int, discord.PermissionOverwrite]]:
        config = await self.guild_config_service.get_guild_config(guild.id)
        membership = config.membership

        wizards_role = guild.get_role(membership.wizards_role_id) if membership.wizards_role_id else None
        unverified_role = guild.get_role(membership.unverified_role_id) if membership.unverified_role_id else None
        os_role = guild.get_role(membership.os_role_id) if membership.os_role_id else None
        voice_role = guild.get_role(membership.voice_role_id) if membership.voice_role_id else None
        special_voice_role = (
            guild.get_role(membership.special_voice_access_role_id)
            if membership.special_voice_access_role_id
            else None
        )
        if wizards_role is None or unverified_role is None:
            return {}

        plans: dict[int, dict[int, discord.PermissionOverwrite]] = {}

        onboarding_target_ids = {
            membership.onboarding_category_id,
            membership.chant_to_start_channel_id,
            membership.verification_channel_id,
        }
        onboarding_target_ids.discard(None)

        onboarding_category = guild.get_channel(membership.onboarding_category_id) if membership.onboarding_category_id else None
        if isinstance(onboarding_category, discord.CategoryChannel):
            plans[onboarding_category.id] = {
                unverified_role.id: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                ),
                wizards_role.id: discord.PermissionOverwrite(view_channel=False),
            }

        for channel_id in (membership.chant_to_start_channel_id, membership.verification_channel_id):
            channel = guild.get_channel(channel_id) if channel_id else None
            if channel is None:
                continue
            channel_plan = {
                unverified_role.id: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    read_message_history=True,
                ),
                wizards_role.id: discord.PermissionOverwrite(
                    view_channel=channel.id == membership.chant_to_start_channel_id,
                    send_messages=False if channel.id == membership.chant_to_start_channel_id else None,
                ),
            }
            if channel.id == membership.chant_to_start_channel_id and os_role is not None:
                channel_plan[os_role.id] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )
            plans[channel.id] = channel_plan

        for channel in guild.channels:
            if channel.id in onboarding_target_ids:
                continue

            policy = self.access.build_wizard_channel_policy(channel, config)
            if not policy:
                continue

            if policy["is_voice_channel"]:
                channel_plan = {
                    unverified_role.id: discord.PermissionOverwrite(view_channel=False),
                    wizards_role.id: discord.PermissionOverwrite(
                        view_channel=policy["wizard_can_view"],
                        connect=policy["wizard_can_connect"],
                        speak=False if policy["wizard_voice_muted"] else None,
                    ),
                }
                if policy["is_restricted_voice_channel"]:
                    if special_voice_role is not None:
                        channel_plan[special_voice_role.id] = discord.PermissionOverwrite(
                            view_channel=True,
                            connect=True,
                        )
                    if voice_role is not None:
                        channel_plan[voice_role.id] = discord.PermissionOverwrite(
                            view_channel=True,
                            connect=True,
                        )
            else:
                channel_plan = {
                    unverified_role.id: discord.PermissionOverwrite(view_channel=False),
                    wizards_role.id: discord.PermissionOverwrite(
                        view_channel=policy["wizard_can_view"],
                        send_messages=True if policy["wizard_can_send"] else None,
                    ),
                }
            plans[channel.id] = channel_plan

        return plans
