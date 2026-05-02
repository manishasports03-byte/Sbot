"""Parallel ticket system cog.

Persistent views and ticket flow are extracted here, but remain inactive until
the modular runtime is deliberately enabled.
"""

from __future__ import annotations

import discord
from discord.ext import commands


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, cog: "TicketsCog"):
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔴")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_id = self.cog.service.get_ticket_owner_id(interaction.channel)
        if owner_id is None:
            await interaction.response.send_message("This is not a valid ticket.", ephemeral=True)
            return

        member = interaction.guild.get_member(owner_id)
        target = member or discord.Object(id=owner_id)

        await interaction.channel.set_permissions(
            target,
            view_channel=False,
            send_messages=False,
            read_message_history=False,
        )
        await interaction.response.edit_message(
            content=None,
            embed=self.cog.service.build_ticket_embed("Ticket", f"Ticket closed by {interaction.user.mention}"),
            view=None,
        )
        await interaction.channel.send(
            embed=self.cog.service.build_ticket_embed("Support team ticket controls", ""),
            view=TicketStaffControlsView(self.cog, owner_id),
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="⚫")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()


class TicketCloseView(discord.ui.View):
    def __init__(self, cog: "TicketsCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ticket_close_prompt")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.cog.service.get_ticket_owner_id(interaction.channel) is None:
            await interaction.response.send_message("This is not a valid ticket.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Are you sure you want to close this ticket?",
            view=TicketCloseConfirmView(self.cog),
        )


class TicketStaffControlsView(discord.ui.View):
    def __init__(self, cog: "TicketsCog", owner_id: int | None = None):
        super().__init__(timeout=None)
        self.cog = cog
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if await self.cog.service.has_ticket_staff_access(interaction.user):
            return True
        await interaction.response.send_message("Only ticket staff can use these controls.", ephemeral=True)
        return False

    @discord.ui.button(label="Open", style=discord.ButtonStyle.secondary, emoji="🔓", custom_id="ticket_staff_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_id = self.owner_id or self.cog.service.get_ticket_owner_id(interaction.channel)
        if owner_id is None:
            await interaction.response.send_message("This is not a valid ticket.", ephemeral=True)
            return

        member = interaction.guild.get_member(owner_id)
        target = member or discord.Object(id=owner_id)
        await interaction.channel.set_permissions(
            target,
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )
        await interaction.response.send_message("Ticket reopened")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑", custom_id="ticket_staff_delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Deleting ticket...", ephemeral=True)
        await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")


class TicketPanelView(discord.ui.View):
    def __init__(self, cog: "TicketsCog"):
        super().__init__(timeout=None)
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        remaining = await self.cog.service.check_create_cooldown(interaction.guild.id, interaction.user.id)
        if remaining is None:
            return True
        await interaction.response.send_message(
            f"Please wait {remaining}s before creating another ticket.",
            ephemeral=True,
        )
        return False

    async def _create_ticket(self, interaction: discord.Interaction, kind: str):
        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        existing_channel = await self.cog.service.find_existing_ticket_channel(interaction.guild, interaction.user.id)
        if existing_channel is not None:
            await interaction.response.send_message(f"Ticket created: {existing_channel.mention}", ephemeral=True)
            return

        await interaction.response.send_message("Creating ticket...", ephemeral=True)
        category_id = await self.cog.service.get_category_id(interaction.guild.id, kind)
        category = interaction.guild.get_channel(category_id) if category_id else None
        if category is None:
            await interaction.edit_original_response(content="Ticket category not found.")
            return

        await category.set_permissions(interaction.guild.default_role, view_channel=False)
        overwrites = await self.cog.service.build_ticket_overwrites(interaction.guild, interaction.user)

        ticket_channel = await interaction.guild.create_text_channel(
            self.cog.service.ticket_channel_name_for(interaction.user),
            category=category,
            topic=f"ticket_owner_id:{interaction.user.id}",
            overwrites=overwrites,
            reason=f"Ticket created by {interaction.user}",
        )
        await ticket_channel.set_permissions(
            interaction.guild.default_role,
            view_channel=False,
            send_messages=False,
            read_message_history=False,
        )
        await ticket_channel.send(
            content=interaction.user.mention,
            embed=self.cog.service.build_ticket_embed(
                "Welcome",
                "Support will be with you shortly.\nTo close this press the close button",
            ),
            view=TicketCloseView(self.cog),
        )
        await self.cog.service.mark_ticket_created(interaction.guild.id, interaction.user.id)
        await interaction.edit_original_response(content=f"Ticket created: {ticket_channel.mention}")

    @discord.ui.button(label="Rewards", style=discord.ButtonStyle.success, emoji="✨", custom_id="ticket_rewards")
    async def rewards_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket(interaction, "rewards")

    @discord.ui.button(label="Staff", style=discord.ButtonStyle.primary, emoji="📩", custom_id="ticket_staff")
    async def staff_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket(interaction, "support")

    @discord.ui.button(label="Support", style=discord.ButtonStyle.danger, emoji="🤝", custom_id="ticket_support")
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket(interaction, "support")


class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.container = bot.container  # type: ignore[attr-defined]
        self.service = self.container.tickets

    async def cog_load(self) -> None:
        self.bot.add_view(TicketPanelView(self))
        self.bot.add_view(TicketCloseView(self))
        self.bot.add_view(TicketStaffControlsView(self))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
