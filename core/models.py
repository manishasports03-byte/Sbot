"""Shared configuration models for the modular architecture."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MembershipConfig:
    verified_role_id: int | None = None
    verified_bonus_role_id: int | None = None
    wizards_role_id: int | None = None
    unverified_role_id: int | None = None
    os_role_id: int | None = None
    voice_role_id: int | None = None
    base_member_role_id: int | None = None
    onboarding_category_id: int | None = None
    chant_to_start_channel_id: int | None = None
    verification_channel_id: int | None = None
    blocked_category_ids: set[int] = field(default_factory=set)
    blocked_channel_ids: set[int] = field(default_factory=set)
    send_category_ids: set[int] = field(default_factory=set)
    allowed_voice_channel_ids: set[int] = field(default_factory=set)
    allowed_voice_category_ids: set[int] = field(default_factory=set)
    muted_voice_category_ids: set[int] = field(default_factory=set)
    view_only_voice_channel_ids: set[int] = field(default_factory=set)
    wizards_voice_category_id: int | None = None
    restricted_voice_channel_id: int | None = None
    special_voice_access_role_id: int | None = None
    join_verify_prompt_delete_seconds: int = 3
    join_visibility_ping_delete_seconds: int = 2

    @classmethod
    def from_payload(cls, payload: dict | None) -> "MembershipConfig":
        payload = dict(payload or {})
        for key in (
            "blocked_category_ids",
            "blocked_channel_ids",
            "send_category_ids",
            "allowed_voice_channel_ids",
            "allowed_voice_category_ids",
            "muted_voice_category_ids",
            "view_only_voice_channel_ids",
        ):
            payload[key] = set(payload.get(key, []))
        return cls(**payload)

    def to_payload(self) -> dict:
        payload = dict(self.__dict__)
        for key in (
            "blocked_category_ids",
            "blocked_channel_ids",
            "send_category_ids",
            "allowed_voice_channel_ids",
            "allowed_voice_category_ids",
            "muted_voice_category_ids",
            "view_only_voice_channel_ids",
        ):
            payload[key] = sorted(payload[key])
        return payload


@dataclass
class TicketConfig:
    panel_channel_id: int | None = None
    panel_title: str = "Create Ticket"
    support_category_id: int | None = None
    rewards_category_id: int | None = None
    helper_role_id: int | None = None
    create_cooldown_seconds: int = 15

    @classmethod
    def from_payload(cls, payload: dict | None) -> "TicketConfig":
        return cls(**dict(payload or {}))

    def to_payload(self) -> dict:
        return dict(self.__dict__)


@dataclass
class RoleBinding:
    source_role_id: int
    target_role_id: int


@dataclass
class GuildConfig:
    guild_id: int
    prefix: str = "."
    membership: MembershipConfig = field(default_factory=MembershipConfig)
    tickets: TicketConfig = field(default_factory=TicketConfig)
