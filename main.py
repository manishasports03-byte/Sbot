"""Parallel modular entrypoint for the staged SBot refactor.

This file is intentionally scaffolded alongside the live monolith in
`bot.py`. The monolith remains the active runtime until the modular path is
validated feature-by-feature.
"""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from core.app import AppContainer
from core.config import load_settings
from core.logging import configure_logging, get_logger


COGS = (
    "cogs.onboarding",
    "cogs.roles",
    "cogs.tickets",
)


def build_bot() -> commands.Bot:
    settings = load_settings()

    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.members = True

    bot = commands.Bot(
        command_prefix=settings.default_prefix,
        intents=intents,
        help_command=None,
    )
    bot.container = AppContainer(settings=settings)  # type: ignore[attr-defined]
    return bot


async def load_cogs(bot: commands.Bot) -> None:
    logger = get_logger("sbot.bootstrap")
    for extension in COGS:
        try:
            await bot.load_extension(extension)
            logger.info("loaded_cog", extra={"cog": extension})
        except Exception:
            logger.exception("failed_to_load_cog", extra={"cog": extension})
            raise


async def run() -> None:
    configure_logging()
    bot = build_bot()
    logger = get_logger("sbot.bootstrap")

    async with bot:
        await bot.container.startup()
        await load_cogs(bot)
        logger.info("modular_runtime_ready", extra={"mode": "parallel_scaffold"})
        await bot.start(bot.container.settings.discord_token)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
