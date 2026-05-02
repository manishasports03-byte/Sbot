"""Service container and lifecycle wiring for the modular bot."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.access import AccessEngine
from core.config import AppSettings
from core.database import Database
from services.guild_config import GuildConfigService
from services.access_runtime import AccessRuntimeService
from services.membership import MembershipService
from services.permission_roles import PermissionRoleService
from services.tickets import TicketService


@dataclass
class AppContainer:
    settings: AppSettings
    database: Database = field(init=False)
    guild_config: GuildConfigService = field(init=False)
    access: AccessEngine = field(init=False)
    memberships: MembershipService = field(init=False)
    permission_roles: PermissionRoleService = field(init=False)
    access_runtime: AccessRuntimeService = field(init=False)
    tickets: TicketService = field(init=False)

    def __post_init__(self) -> None:
        self.database = Database(self.settings.database_url)
        self.guild_config = GuildConfigService(self.database)
        self.access = AccessEngine(self.guild_config)
        self.memberships = MembershipService(self.guild_config, self.access)
        self.permission_roles = PermissionRoleService(self.guild_config, self.access)
        self.access_runtime = AccessRuntimeService(self.memberships, self.permission_roles, self.access)
        self.tickets = TicketService(self.guild_config, self.access)

    async def startup(self) -> None:
        await self.database.connect()
        await self.database.ensure_schema()
        await self.guild_config.ensure_schema()

    async def shutdown(self) -> None:
        await self.database.close()
