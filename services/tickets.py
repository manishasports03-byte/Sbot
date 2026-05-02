"""Ticket permission and payload service."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import discord


class TicketService:
    def __init__(self, guild_config_service, access_engine):
        self.guild_config_service = guild_config_service
        self.access = access_engine
        self.button_cooldowns: dict[int, object] = {}

    async def build_ticket_overwrites(self, guild: discord.Guild, owner: discord.Member) -> dict:
        config = await self.guild_config_service.get_guild_config(guild.id)
        helper_role = guild.get_role(config.tickets.helper_role_id) if config.tickets.helper_role_id else None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            owner: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                )

        if helper_role is not None:
            overwrites[helper_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        return overwrites

    async def check_create_cooldown(self, guild_id: int, user_id: int) -> int | None:
        _ = guild_id
        now = datetime.now(timezone.utc)
        expires_at = self.button_cooldowns.get(user_id)
        if expires_at and now < expires_at:
            return int((expires_at - now).total_seconds())
        return None

    async def mark_ticket_created(self, guild_id: int, user_id: int) -> None:
        config = await self.guild_config_service.get_guild_config(guild_id)
        self.button_cooldowns[user_id] = datetime.now(timezone.utc) + timedelta(
            seconds=config.tickets.create_cooldown_seconds
        )

    async def has_ticket_staff_access(self, member) -> bool:
        if member.guild_permissions.administrator:
            return True

        config = await self.guild_config_service.get_guild_config(member.guild.id)
        helper_role_id = config.tickets.helper_role_id
        return helper_role_id is not None and self.access.member_has_role(member, helper_role_id)

    async def get_panel_channel_id(self, guild_id: int) -> int | None:
        config = await self.guild_config_service.get_guild_config(guild_id)
        return config.tickets.panel_channel_id

    async def get_panel_title(self, guild_id: int) -> str:
        config = await self.guild_config_service.get_guild_config(guild_id)
        return config.tickets.panel_title

    async def get_category_id(self, guild_id: int, kind: str) -> int | None:
        config = await self.guild_config_service.get_guild_config(guild_id)
        if kind == "rewards":
            return config.tickets.rewards_category_id
        return config.tickets.support_category_id

    @staticmethod
    def build_ticket_embed(title: str, description: str, footer: str | None = None) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
        if footer:
            embed.set_footer(text=footer)
        return embed

    async def build_panel_embed(self, guild_id: int) -> discord.Embed:
        title = await self.get_panel_title(guild_id)
        return self.build_ticket_embed(
            title,
            "To create a ticket use the buttons below 🙂\n\nHave patience after creating a ticket 🤍",
            "whAlien - Ticket System",
        )

    @staticmethod
    def ticket_channel_name_for(user) -> str:
        safe_name = re.sub(r"[^a-z0-9-]", "-", user.name.lower()).strip("-") or "user"
        return f"ticket-{safe_name}"

    @staticmethod
    def get_ticket_owner_id(channel) -> int | None:
        if not channel or not channel.topic or not channel.topic.startswith("ticket_owner_id:"):
            return None
        try:
            return int(channel.topic.split(":", 1)[1])
        except ValueError:
            return None

    async def find_existing_ticket_channel(self, guild, user_id: int):
        config = await self.guild_config_service.get_guild_config(guild.id)
        for category_id in (config.tickets.support_category_id, config.tickets.rewards_category_id):
            category = guild.get_channel(category_id) if category_id else None
            if category is None:
                continue
            for channel in category.text_channels:
                if self.get_ticket_owner_id(channel) == user_id:
                    return channel
        return None
