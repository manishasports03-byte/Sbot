"""Environment-backed app settings for the modular runtime."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class AppSettings:
    discord_token: str
    database_url: str
    default_prefix: str = "."
    log_level: str = "INFO"
    modular_handlers_enabled: bool = False
    modular_shadow_mode: bool = False


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> AppSettings:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set. Add it to .env before starting the bot.")

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Add it to .env before starting the bot.")

    return AppSettings(
        discord_token=token,
        database_url=database_url,
        default_prefix=os.getenv("DEFAULT_PREFIX", ".").strip() or ".",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip() or "INFO",
        modular_handlers_enabled=_env_flag("MODULAR_HANDLERS_ENABLED", False),
        modular_shadow_mode=_env_flag("MODULAR_SHADOW_MODE", False),
    )
