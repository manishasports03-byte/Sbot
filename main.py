"""Compatibility launcher for the restored monolithic bot."""

from __future__ import annotations

from discord.ext import commands

orig_run = commands.Bot.run
commands.Bot.run = lambda self, *args, **kwargs: None
try:
    import bot as monolith
finally:
    commands.Bot.run = orig_run


def main() -> None:
    monolith.bot.run(monolith.token)


if __name__ == "__main__":
    main()
