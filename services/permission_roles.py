"""Hidden permission-role synchronization service."""

from __future__ import annotations

from core.models import RoleBinding


class PermissionRoleService:
    def __init__(self, guild_config_service, access_engine):
        self.guild_config_service = guild_config_service
        self.access = access_engine

    async def resolve_member_bindings(self, member) -> set[int]:
        bindings = await self.guild_config_service.get_role_bindings(member.guild.id)
        return self.access.resolve_desired_target_roles(member, bindings)

    async def get_effective_bindings(self, guild_id: int) -> list[RoleBinding]:
        return await self.guild_config_service.get_role_bindings(guild_id)

    async def plan_role_sync(self, member) -> dict[str, list[int]]:
        bindings = await self.get_effective_bindings(member.guild.id)
        if not bindings:
            return {"add": [], "remove": []}

        managed_target_ids = {binding.target_role_id for binding in bindings}
        desired_target_ids = self.access.resolve_desired_target_roles(member, bindings)
        current_role_ids = {role.id for role in member.roles}

        roles_to_add = sorted(desired_target_ids - current_role_ids)
        roles_to_remove = sorted((managed_target_ids - desired_target_ids) & current_role_ids)
        return {"add": roles_to_add, "remove": roles_to_remove}
