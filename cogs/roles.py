"""Compatibility cog kept for phased migration.

Member role synchronization now routes through the centralized modular access
runtime in `OnboardingCog` to avoid duplicate actions.
"""

from __future__ import annotations

from discord.ext import commands


class RolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RolesCog(bot))
