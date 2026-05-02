"""Centralized access and permission helpers."""

from __future__ import annotations

from collections.abc import Iterable

import discord

from core.models import GuildConfig, RoleBinding


class AccessEngine:
    def __init__(self, guild_config_service):
        self.guild_config_service = guild_config_service

    @staticmethod
    def member_has_role(member, role_id: int | None) -> bool:
        if role_id is None:
            return False
        return any(role.id == role_id for role in member.roles)

    @staticmethod
    def member_has_any_role(member, role_ids: Iterable[int]) -> bool:
        allowed = set(role_ids)
        if not allowed:
            return False
        return any(role.id in allowed for role in member.roles)

    def can_use_role_gated_command(self, member, *role_ids: int) -> bool:
        if member.guild.owner_id == member.id:
            return True
        return self.member_has_any_role(member, role_ids)

    @staticmethod
    def resolve_desired_target_roles(member, bindings: list[RoleBinding]) -> set[int]:
        member_role_ids = {role.id for role in member.roles}
        return {
            binding.target_role_id
            for binding in bindings
            if binding.source_role_id in member_role_ids
        }

    @staticmethod
    def is_verified_member(member, config: GuildConfig) -> bool:
        membership = config.membership
        verified = AccessEngine.member_has_role(member, membership.verified_role_id)
        wizarded = AccessEngine.member_has_role(member, membership.wizards_role_id)
        return verified or wizarded

    def plan_membership_role_sync(self, member, config: GuildConfig) -> tuple[list[int], list[int]]:
        membership = config.membership
        roles_to_add: list[int] = []
        roles_to_remove: list[int] = []

        has_verified = self.member_has_role(member, membership.verified_role_id)
        has_wizards = self.member_has_role(member, membership.wizards_role_id)
        has_unverified = self.member_has_role(member, membership.unverified_role_id)

        if has_verified and membership.wizards_role_id and not has_wizards:
            roles_to_add.append(membership.wizards_role_id)

        if has_verified or has_wizards:
            if has_unverified and membership.unverified_role_id:
                roles_to_remove.append(membership.unverified_role_id)
        elif membership.unverified_role_id and not has_unverified:
            roles_to_add.append(membership.unverified_role_id)

        return roles_to_add, roles_to_remove

    def plan_base_role_sync(self, member, config: GuildConfig) -> tuple[list[int], list[int]]:
        membership = config.membership
        base_role_id = membership.base_member_role_id
        if not base_role_id:
            return [], []

        is_verified_member = self.is_verified_member(member, config)
        is_unverified_member = self.member_has_role(member, membership.unverified_role_id)
        has_base_role = self.member_has_role(member, base_role_id)

        if is_verified_member and not is_unverified_member:
            if not has_base_role:
                return [base_role_id], []
            return [], []

        if has_base_role:
            return [], [base_role_id]
        return [], []

    def build_wizard_channel_policy(self, channel, config: GuildConfig) -> dict[str, bool | None]:
        membership = config.membership
        channel_category_id = getattr(channel, "category_id", None)
        is_voice_channel = isinstance(channel, (discord.VoiceChannel, discord.StageChannel))

        wizard_can_view = (
            channel.id not in membership.blocked_channel_ids
            and channel.id not in membership.blocked_category_ids
            and channel_category_id not in membership.blocked_category_ids
        )
        if channel_category_id in membership.send_category_ids:
            wizard_can_view = True

        wizard_can_send = (
            channel.id in membership.send_category_ids
            or channel_category_id in membership.send_category_ids
        )

        if is_voice_channel and channel.id in membership.view_only_voice_channel_ids:
            wizard_can_view = True

        wizard_can_connect = (
            channel.id in membership.allowed_voice_channel_ids
            or channel_category_id in membership.allowed_voice_category_ids
            or (
                channel_category_id == membership.wizards_voice_category_id
                and channel.id != membership.restricted_voice_channel_id
            )
        )

        if channel.id in membership.view_only_voice_channel_ids:
            wizard_can_connect = False

        wizard_voice_muted = channel_category_id in membership.muted_voice_category_ids
        return {
            "is_voice_channel": is_voice_channel,
            "wizard_can_view": wizard_can_view,
            "wizard_can_send": wizard_can_send,
            "wizard_can_connect": wizard_can_connect,
            "wizard_voice_muted": wizard_voice_muted,
            "is_restricted_voice_channel": channel.id == membership.restricted_voice_channel_id,
        }
