import os
import random
import re
import copy
import io
import asyncpg
import aiohttp
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import asyncio

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PREFIX = "."
BOT_START_TIME = datetime.now(timezone.utc)


def get_command_prefix(bot_instance, message):
    if not message.guild:
        return DEFAULT_PREFIX
    return guild_prefix_cache.get(message.guild.id, DEFAULT_PREFIX)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=get_command_prefix, intents=intents, help_command=None)

# ===== CONFIG =====
bad_words = ["mc", "bc", "madarchod", "bhosdike", "chutiya", "idiot", "stupid"]

# ===== INVITE TRACKING CONFIG =====
db = None
guild_prefix_cache = {}
server_invites = {}  # {guild_id: {invite_code: invite_object}}
INVITE_UI_COLOR = discord.Color.from_str("#2b2d31")
INVITED_PAGE_SIZE = 5
LEADERBOARD_PAGE_SIZE = 10
STARTUP_NOTICE_CHANNEL_ID = 1379052516863381638
STARTUP_NOTIFY_USER_IDS = (760729575789166652, 1476689941252800676)
startup_notice_sent = False
MESSAGE_DAILY_RESET_KEY = "message_daily_reset_date"
NO_PREFIX_DISABLED_CHANNEL_ID = 1379052516863381638
NO_PREFIX_COMMANDS = {
    "about", "info", "botinfo", "ping", "invite",
    "serverinfo", "userinfo", "roleinfo", "vcinfo", "avatar", "av", "banner", "guildbanner",
    "membercount", "shards", "permissions", "accountage", "uptime", "stats", "setup",
    "tickets", "sendtickets", "modlogs",
    "invites", "inv", "i", "inviter", "invited", "inviteinfo",
    "addinvites", "removeinvites", "clearinvites", "resetmyinvites",
    "messages", "m", "addmessages", "removemessages",
    "blacklistchannel", "unblacklistchannel", "blacklistedchannels", "clearmessages", "resetmymessages",
    "autoresponder", "autoreact", "sticky",
    "lb", "leaderboard",
    "warn", "mute", "unmute", "kick", "ban", "purge", "slowmode",
    "gstart", "gend", "greroll",
    "steal",
}

# ===== ACTIVITY ROTATION =====
ACTIVITY_MESSAGES = [
    "with whAlien ✨",
    ".commands | Help Menu",
    "Serving users 🚀",
    "Made by @_anuneet1x 🤍"
]
current_activity_index = 0

# ===== TEMP VC CONFIG =====
TEMP_VC_CATEGORY_NAME = "Temporary Channels"
TEMP_VC_PARENT_CHANNEL_ID = None  # Set to parent category ID if you have one
temp_vc_users = {}  # {user_id: channel_id}

# ===== TICKETS CONFIG =====
TICKET_PANEL_CHANNEL_ID = 1379498807288529007
TICKET_SUPPORT_CATEGORY_ID = 1379497343765844218
TICKET_REWARDS_CATEGORY_ID = 1496957253117415555
TICKET_PANEL_MESSAGE_KEY = "ticket_panel_message_id"
TICKET_PANEL_TITLE = "Create Ticket"
TICKET_BUTTON_COOLDOWN_SECONDS = 15
ticket_button_cooldowns = {}
MEDIA_ONLY_CHANNEL_ID = 1379065330957160560
VERIFIED_ROLE_ID = 1442882228802551971
VERIFIED_BONUS_ROLE_ID = 1499789428703363275
WIZARDS_ROLE_ID = 1499789428703363275
UNVERIFIED_ROLE_ID = 1442881420182683770
ONBOARDING_CATEGORY_ID = 1379780404894236744
CHANT_TO_START_CHANNEL_ID = 1379780588193448027
SECURITY_VERIFICATION_CHANNEL_ID = 1442881449434026045
BLOCKED_WIZARDS_CATEGORY_IDS = {
    1391451602178801766,
    1379076786226462772,
}
BIRTHDAY_ROLE_ID = 1380464856016097341
VIRELYA_ROLE_ID = 1499783835594788894
SEARASTA_ROLE_ID = 1499785700533473290
ARCHWIZARD_ROLE_ID = 1499785874559209532
OS_ROLE_ID = 1499980794133876857
REQ_ROLE_ID = 1499993788452569129
KICK_ROLE_ID = 1499994064425324594
MUTE_ROLE_ID = 1499994184801845370
BAN_ROLE_ID = 1499994263084339350
VOICE_ROLE_ID = 1499994335360323645
MEDIA_ROLE_ID = 1499994927168225330
HIGH_ARCANIST_ROLE_ID = 1499786167749578943
NEBULARC_ROLE_ID = 1499786383265370143
SPELLWARDEN_ROLE_ID = 1499786512433156136
ENIGMANCER_ROLE_ID = 1499786767090319522
ECHOKEEPER_ROLE_ID = 1499786856324137091
MELODIST_ROLE_ID = 1499787024750743623
APPOLO_ROLE_ID = 1499787129532842004
ECLIPSEBOUND_ELITE_ROLE_ID = 1499787129532842004
NOVA_WATCH_ROLE_ID = 1499787241030160394
DEFAULT_PERMISSION_ROLE_LINKS = (
    (VIRELYA_ROLE_ID, OS_ROLE_ID),
    (SEARASTA_ROLE_ID, OS_ROLE_ID),
    (ARCHWIZARD_ROLE_ID, OS_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, REQ_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, KICK_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, MUTE_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, BAN_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, VOICE_ROLE_ID),
    (NEBULARC_ROLE_ID, KICK_ROLE_ID),
    (NEBULARC_ROLE_ID, MUTE_ROLE_ID),
    (NEBULARC_ROLE_ID, BAN_ROLE_ID),
    (NEBULARC_ROLE_ID, VOICE_ROLE_ID),
    (SPELLWARDEN_ROLE_ID, KICK_ROLE_ID),
    (SPELLWARDEN_ROLE_ID, MUTE_ROLE_ID),
    (SPELLWARDEN_ROLE_ID, VOICE_ROLE_ID),
    (ECHOKEEPER_ROLE_ID, VOICE_ROLE_ID),
    (MELODIST_ROLE_ID, MEDIA_ROLE_ID),
    (APPOLO_ROLE_ID, MEDIA_ROLE_ID),
)
IST = timezone(timedelta(hours=5, minutes=30))
AUTORESPONDER_COOLDOWN_SECONDS = 2
autoresponder_cooldowns = {}
LINK_FILTER_GUILD_ID = 1218837762753564722
URL_PATTERN = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE)
DISCORD_INVITE_PATTERN = re.compile(
    r"(discord\.gg/[A-Za-z0-9-]+|discord(?:app)?\.com/invite/[A-Za-z0-9-]+)",
    re.IGNORECASE,
)
NSFW_DOMAIN_KEYWORDS = (
    "porn",
    "xvideos",
    "xnxx",
    "xhamster",
    "redtube",
    "youporn",
    "pornhub",
    "sex",
    "hentai",
    "rule34",
    "onlyfans",
    "nsfw",
)

# ===== GIVEAWAY CONFIG =====
giveaways = {}  # {message_id: {"message_id": int, "channel_id": int, "guild_id": int, "end_time": datetime, "winners": int, "prize": str, "ended": bool, "task": asyncio.Task | None}}

# ===== SECURITY CONFIG =====
spam_tracker = defaultdict(list)  # {user_id: [timestamps]}
SPAM_THRESHOLD = 5  # messages in SPAM_WINDOW
SPAM_WINDOW = 5  # seconds
SPAM_MUTE_DURATION = 300  # 5 minutes
# ===== MODERATION CONFIG =====
warnings = defaultdict(lambda: defaultdict(int))  # {guild_id: {user_id: count}}
moderation_logs = defaultdict(list)  # {guild_id: [log_entries]}


def message_has_blocked_link(message_content):
    lowered_content = message_content.lower()
    if DISCORD_INVITE_PATTERN.search(lowered_content):
        return True

    for url in URL_PATTERN.findall(lowered_content):
        normalized_url = url.lower().strip("()[]<>.,!?\"'")
        if any(keyword in normalized_url for keyword in NSFW_DOMAIN_KEYWORDS):
            return True

    return False


async def load_guild_prefixes():
    """Load guild prefixes from PostgreSQL into cache."""
    guild_prefix_cache.clear()
    rows = await db_fetch("SELECT guild_id, prefix FROM guild_settings", log_fetch=False) or []
    for row in rows:
        guild_prefix_cache[row["guild_id"]] = row["prefix"] or DEFAULT_PREFIX


async def db_execute(query, *args, log_context=None):
    if db is None:
        print("DATABASE ERROR: database pool is not available")
        return None
    try:
        async with db.acquire() as conn:
            result = await conn.execute(query, *args)
            if log_context:
                print(log_context)
            return result
    except Exception as e:
        print("DATABASE ERROR:", e)
        return None


async def db_fetch(query, *args, log_fetch=True):
    if db is None:
        print("DATABASE ERROR: database pool is not available")
        return []
    try:
        async with db.acquire() as conn:
            result = await conn.fetch(query, *args)
            if log_fetch:
                print("Fetched data:", result)
            return result
    except Exception as e:
        print("DATABASE ERROR:", e)
        return []


async def db_fetchrow(query, *args, log_fetch=True):
    if db is None:
        print("DATABASE ERROR: database pool is not available")
        return None
    try:
        async with db.acquire() as conn:
            result = await conn.fetchrow(query, *args)
            if log_fetch:
                print("Fetched data:", result)
            return result
    except Exception as e:
        print("DATABASE ERROR:", e)
        return None


async def db_fetchval(query, *args, log_fetch=True):
    if db is None:
        print("DATABASE ERROR: database pool is not available")
        return None
    try:
        async with db.acquire() as conn:
            result = await conn.fetchval(query, *args)
            if log_fetch:
                print("Fetched data:", result)
            return result
    except Exception as e:
        print("DATABASE ERROR:", e)
        return None


async def create_tables():
    """Initialize PostgreSQL tables for persistent bot stats"""
    await db_execute("""
        CREATE TABLE IF NOT EXISTS invite_stats (
            guild_id BIGINT,
            user_id BIGINT,
            invites INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS inviter_map (
            guild_id BIGINT,
            user_id BIGINT,
            inviter_id BIGINT,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS message_stats (
            guild_id BIGINT,
            user_id BIGINT,
            messages INTEGER DEFAULT 0,
            daily_messages INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS message_blacklist (
            guild_id BIGINT,
            channel_id BIGINT,
            PRIMARY KEY (guild_id, channel_id)
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id BIGINT PRIMARY KEY,
            prefix TEXT DEFAULT '.'
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS afk_users (
            guild_id BIGINT,
            user_id BIGINT,
            reason TEXT,
            timestamp BIGINT,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS custom_role_settings (
            guild_id BIGINT PRIMARY KEY,
            role_id BIGINT
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS autoresponders (
            guild_id BIGINT,
            trigger TEXT,
            response TEXT,
            PRIMARY KEY (guild_id, trigger)
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS auto_reactions (
            guild_id BIGINT,
            trigger TEXT,
            emoji TEXT,
            PRIMARY KEY (guild_id, trigger)
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS sticky_messages (
            guild_id BIGINT PRIMARY KEY,
            message TEXT
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS birthday_users (
            guild_id BIGINT,
            user_id BIGINT,
            birth_month INTEGER,
            birth_day INTEGER,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    await db_execute("""
        CREATE TABLE IF NOT EXISTS permission_role_links (
            guild_id BIGINT,
            source_role_id BIGINT,
            target_role_id BIGINT,
            PRIMARY KEY (guild_id, source_role_id, target_role_id)
        )
    """)
    print("Tables ensured/created")


async def connect_db():
    global db
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE ERROR: DATABASE_URL is not set")
        return

    if db is not None:
        return

    print("Connecting to PostgreSQL...")
    try:
        db = await asyncpg.create_pool(database_url)
        print("PostgreSQL connected successfully")
        await create_tables()
        await load_guild_prefixes()
        await load_afk_users()
        print("Database initialized successfully")
    except Exception as e:
        db = None
        print("DATABASE ERROR:", e)

async def get_invites(guild_id, user_id):
    """Get invite count for a user."""
    return await db_fetchval(
        "SELECT invites FROM invite_stats WHERE guild_id = $1 AND user_id = $2",
        guild_id,
        user_id,
    ) or 0


async def add_invites(guild_id, user_id, amount):
    """Add invites to a user."""
    current = await get_invites(guild_id, user_id)
    new_total = max(0, current + amount)
    await db_execute(
        """
        INSERT INTO invite_stats (guild_id, user_id, invites)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, user_id)
        DO UPDATE SET invites = EXCLUDED.invites
        """,
        guild_id,
        user_id,
        new_total,
        log_context=f"Saved invites for user: {user_id}",
    )
    return new_total


async def set_inviter(guild_id, user_id, inviter_id):
    """Set who invited a user."""
    await db_execute(
        """
        INSERT INTO inviter_map (guild_id, user_id, inviter_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, user_id)
        DO UPDATE SET inviter_id = EXCLUDED.inviter_id
        """,
        guild_id,
        user_id,
        inviter_id,
        log_context=f"Saved inviter mapping for user: {user_id}",
    )


async def get_inviter(guild_id, user_id):
    """Get who invited a user."""
    return await db_fetchval(
        "SELECT inviter_id FROM inviter_map WHERE guild_id = $1 AND user_id = $2",
        guild_id,
        user_id,
    )


async def get_invited_users(guild_id, inviter_id):
    """Get list of users invited by someone."""
    rows = await db_fetch(
        "SELECT user_id FROM inviter_map WHERE guild_id = $1 AND inviter_id = $2 ORDER BY user_id",
        guild_id,
        inviter_id,
    )
    return [row["user_id"] for row in rows]


async def get_leaderboard(guild_id, limit=10):
    """Get top inviters for a guild."""
    if limit is None:
        rows = await db_fetch(
            "SELECT user_id, invites FROM invite_stats WHERE guild_id = $1 ORDER BY invites DESC, user_id ASC",
            guild_id,
        )
    else:
        rows = await db_fetch(
            "SELECT user_id, invites FROM invite_stats WHERE guild_id = $1 ORDER BY invites DESC, user_id ASC LIMIT $2",
            guild_id,
            limit,
        )
    return [(row["user_id"], row["invites"]) for row in rows]


async def clear_invite_data(guild_id):
    """Clear all invite data for a guild."""
    await db_execute("DELETE FROM invite_stats WHERE guild_id = $1", guild_id, log_context=f"Cleared invite stats for guild: {guild_id}")
    await db_execute("DELETE FROM inviter_map WHERE guild_id = $1", guild_id, log_context=f"Cleared inviter map for guild: {guild_id}")


async def reset_user_invites(guild_id, user_id):
    """Reset invite count for one user."""
    await db_execute(
        "DELETE FROM invite_stats WHERE guild_id = $1 AND user_id = $2",
        guild_id,
        user_id,
        log_context=f"Reset invites for user: {user_id}",
    )


async def get_state_value(key):
    return await db_fetchval("SELECT value FROM bot_state WHERE key = $1", key)


async def set_state_value(key, value):
    await db_execute(
        """
        INSERT INTO bot_state (key, value)
        VALUES ($1, $2)
        ON CONFLICT (key)
        DO UPDATE SET value = EXCLUDED.value
        """,
        key,
        value,
        log_context=f"Saved bot state key: {key}",
    )


async def set_custom_role(guild_id, role_id):
    await db_execute(
        """
        INSERT INTO custom_role_settings (guild_id, role_id)
        VALUES ($1, $2)
        ON CONFLICT (guild_id)
        DO UPDATE SET role_id = EXCLUDED.role_id
        """,
        guild_id,
        role_id,
        log_context=f"Saved custom role for guild: {guild_id}",
    )


async def remove_custom_role(guild_id, role_id=None):
    if role_id is None:
        await db_execute(
            "DELETE FROM custom_role_settings WHERE guild_id = $1",
            guild_id,
            log_context=f"Removed custom role config for guild: {guild_id}",
        )
        return

    await db_execute(
        "DELETE FROM custom_role_settings WHERE guild_id = $1 AND role_id = $2",
        guild_id,
        role_id,
        log_context=f"Removed custom role {role_id} for guild: {guild_id}",
    )


async def get_custom_role_id(guild_id):
    return await db_fetchval(
        "SELECT role_id FROM custom_role_settings WHERE guild_id = $1",
        guild_id,
    )


async def sync_base_role_for_member(member):
    if member.bot:
        return

    role_id = await get_custom_role_id(member.guild.id)
    if not role_id:
        return

    verified_role = member.guild.get_role(VERIFIED_ROLE_ID)
    wizards_role = member.guild.get_role(WIZARDS_ROLE_ID)
    unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
    role = member.guild.get_role(role_id)
    if role is None:
        return

    has_base_role = role in member.roles
    is_verified_member = (
        (verified_role is not None and verified_role in member.roles)
        or (wizards_role is not None and wizards_role in member.roles)
    )
    is_unverified_member = unverified_role is not None and unverified_role in member.roles

    if is_verified_member and not is_unverified_member:
        if has_base_role:
            return
        try:
            await member.add_roles(role, reason="Auto-assigned base member role")
        except discord.Forbidden:
            print(f"Missing permissions to assign base role for {member}")
        except discord.HTTPException:
            print(f"Failed to assign base role for {member}")
        return

    if not has_base_role:
        return

    try:
        await member.remove_roles(role, reason="Removed base role until member is verified")
    except discord.Forbidden:
        print(f"Missing permissions to remove base role for {member}")
    except discord.HTTPException:
        print(f"Failed to remove base role for {member}")


async def sync_base_roles_for_guild(guild):
    role_id = await get_custom_role_id(guild.id)
    if not role_id:
        return

    role = guild.get_role(role_id)
    if role is None:
        return

    for member in guild.members:
        if member.bot:
            continue
        await sync_base_role_for_member(member)


async def sync_base_roles_for_all_guilds():
    for guild in bot.guilds:
        await sync_base_roles_for_guild(guild)


async def add_autoresponder(guild_id, trigger, response):
    normalized_trigger = trigger.lower()
    await db_execute(
        """
        INSERT INTO autoresponders (guild_id, trigger, response)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, trigger)
        DO UPDATE SET response = EXCLUDED.response
        """,
        guild_id,
        normalized_trigger,
        response,
        log_context=f"Saved autoresponder '{normalized_trigger}' for guild: {guild_id}",
    )


async def remove_autoresponder(guild_id, trigger):
    await db_execute(
        "DELETE FROM autoresponders WHERE guild_id = $1 AND trigger = $2",
        guild_id,
        trigger.lower(),
        log_context=f"Removed autoresponder '{trigger.lower()}' for guild: {guild_id}",
    )


async def get_autoresponders(guild_id):
    rows = await db_fetch(
        "SELECT trigger, response FROM autoresponders WHERE guild_id = $1 ORDER BY trigger ASC",
        guild_id,
    )
    return [(row["trigger"], row["response"]) for row in rows]


async def add_auto_reaction(guild_id, trigger, emoji):
    normalized_trigger = trigger.lower()
    await db_execute(
        """
        INSERT INTO auto_reactions (guild_id, trigger, emoji)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, trigger)
        DO UPDATE SET emoji = EXCLUDED.emoji
        """,
        guild_id,
        normalized_trigger,
        emoji,
        log_context=f"Saved autoreact '{normalized_trigger}' for guild: {guild_id}",
    )


async def remove_auto_reaction(guild_id, trigger):
    await db_execute(
        "DELETE FROM auto_reactions WHERE guild_id = $1 AND trigger = $2",
        guild_id,
        trigger.lower(),
        log_context=f"Removed autoreact '{trigger.lower()}' for guild: {guild_id}",
    )


async def get_auto_reactions(guild_id):
    rows = await db_fetch(
        "SELECT trigger, emoji FROM auto_reactions WHERE guild_id = $1 ORDER BY trigger ASC",
        guild_id,
    )
    return [(row["trigger"], row["emoji"]) for row in rows]


async def set_sticky_message(guild_id, message):
    await db_execute(
        """
        INSERT INTO sticky_messages (guild_id, message)
        VALUES ($1, $2)
        ON CONFLICT (guild_id)
        DO UPDATE SET message = EXCLUDED.message
        """,
        guild_id,
        message,
        log_context=f"Saved sticky message for guild: {guild_id}",
    )


async def remove_sticky_message(guild_id):
    await db_execute(
        "DELETE FROM sticky_messages WHERE guild_id = $1",
        guild_id,
        log_context=f"Removed sticky message for guild: {guild_id}",
    )


async def get_sticky_message(guild_id):
    return await db_fetchval(
        "SELECT message FROM sticky_messages WHERE guild_id = $1",
        guild_id,
    )


async def reset_daily_message_counts_if_needed():
    today = datetime.now(timezone.utc).date().isoformat()
    last_reset = await get_state_value(MESSAGE_DAILY_RESET_KEY)
    if last_reset == today:
        return

    await db_execute("UPDATE message_stats SET daily_messages = 0", log_context="Reset daily message counts")
    await set_state_value(MESSAGE_DAILY_RESET_KEY, today)


async def set_birthday(guild_id, user_id, birth_month, birth_day):
    await db_execute(
        """
        INSERT INTO birthday_users (guild_id, user_id, birth_month, birth_day)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (guild_id, user_id)
        DO UPDATE SET
            birth_month = EXCLUDED.birth_month,
            birth_day = EXCLUDED.birth_day
        """,
        guild_id,
        user_id,
        birth_month,
        birth_day,
        log_context=f"Saved birthday for user {user_id} in guild {guild_id}",
    )


async def remove_birthday(guild_id, user_id):
    await db_execute(
        "DELETE FROM birthday_users WHERE guild_id = $1 AND user_id = $2",
        guild_id,
        user_id,
        log_context=f"Removed birthday for user {user_id} in guild {guild_id}",
    )


async def get_birthday(guild_id, user_id):
    return await db_fetchrow(
        "SELECT birth_month, birth_day FROM birthday_users WHERE guild_id = $1 AND user_id = $2",
        guild_id,
        user_id,
        log_fetch=False,
    )


async def get_birthdays_for_day(birth_month, birth_day):
    return await db_fetch(
        "SELECT guild_id, user_id FROM birthday_users WHERE birth_month = $1 AND birth_day = $2",
        birth_month,
        birth_day,
        log_fetch=False,
    )


def get_ist_today():
    return datetime.now(IST).date()


async def add_permission_role_link(guild_id, source_role_id, target_role_id):
    await db_execute(
        """
        INSERT INTO permission_role_links (guild_id, source_role_id, target_role_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, source_role_id, target_role_id)
        DO NOTHING
        """,
        guild_id,
        source_role_id,
        target_role_id,
        log_context=f"Saved permission role link {source_role_id} -> {target_role_id} in guild {guild_id}",
    )


async def remove_permission_role_link(guild_id, source_role_id, target_role_id):
    await db_execute(
        "DELETE FROM permission_role_links WHERE guild_id = $1 AND source_role_id = $2 AND target_role_id = $3",
        guild_id,
        source_role_id,
        target_role_id,
        log_context=f"Removed permission role link {source_role_id} -> {target_role_id} in guild {guild_id}",
    )


async def get_permission_role_links(guild_id):
    return await db_fetch(
        """
        SELECT source_role_id, target_role_id
        FROM permission_role_links
        WHERE guild_id = $1
        ORDER BY target_role_id, source_role_id
        """,
        guild_id,
        log_fetch=False,
    )


async def get_effective_permission_role_links(guild_id):
    links = {(source_role_id, target_role_id) for source_role_id, target_role_id in DEFAULT_PERMISSION_ROLE_LINKS}

    for row in await get_permission_role_links(guild_id):
        links.add((row["source_role_id"], row["target_role_id"]))

    return [
        {"source_role_id": source_role_id, "target_role_id": target_role_id}
        for source_role_id, target_role_id in sorted(links, key=lambda pair: (pair[1], pair[0]))
    ]


async def get_message_stats(guild_id, user_id):
    await reset_daily_message_counts_if_needed()
    row = await db_fetchrow(
        "SELECT messages, daily_messages FROM message_stats WHERE guild_id = $1 AND user_id = $2",
        guild_id,
        user_id,
    )
    if row:
        return {"messages": row["messages"], "daily_messages": row["daily_messages"]}
    return {"messages": 0, "daily_messages": 0}


async def set_message_stats(guild_id, user_id, messages, daily_messages):
    await db_execute(
        """
        INSERT INTO message_stats (guild_id, user_id, messages, daily_messages)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (guild_id, user_id)
        DO UPDATE SET
            messages = EXCLUDED.messages,
            daily_messages = EXCLUDED.daily_messages
        """,
        guild_id,
        user_id,
        max(0, messages),
        max(0, daily_messages),
        log_context=f"Saved message stats for user: {user_id}",
    )


async def add_messages(guild_id, user_id, amount, update_daily=False):
    stats = await get_message_stats(guild_id, user_id)
    new_total = max(0, stats["messages"] + amount)
    daily_change = amount if update_daily and amount > 0 else 0
    new_daily_total = max(0, stats["daily_messages"] + daily_change)
    await set_message_stats(guild_id, user_id, new_total, new_daily_total)
    return {"messages": new_total, "daily_messages": new_daily_total}


async def increment_message_count(guild_id, user_id):
    stats = await get_message_stats(guild_id, user_id)
    new_total = stats["messages"] + 1
    new_daily_total = stats["daily_messages"] + 1
    await set_message_stats(guild_id, user_id, new_total, new_daily_total)
    return {"messages": new_total, "daily_messages": new_daily_total}


async def add_message(guild_id, user_id):
    """Persist one newly observed message."""
    result = await increment_message_count(guild_id, user_id)
    print("Saved message for user:", user_id)
    return result


async def get_messages(guild_id, user_id):
    """Fetch persisted message totals for one user."""
    return await get_message_stats(guild_id, user_id)


async def reset_messages(guild_id, user_id):
    """Reset persisted message totals for one user."""
    await reset_user_messages(guild_id, user_id)


async def leaderboard_messages(guild_id, column="messages", limit=10):
    """Fetch the persisted message leaderboard."""
    return await get_message_leaderboard(guild_id, column=column, limit=limit)


async def clear_all_messages(guild_id):
    await db_execute("DELETE FROM message_stats WHERE guild_id = $1", guild_id, log_context=f"Cleared message stats for guild: {guild_id}")


async def reset_user_messages(guild_id, user_id):
    await set_message_stats(guild_id, user_id, 0, 0)


async def get_message_leaderboard(guild_id, column="messages", limit=10):
    if column not in {"messages", "daily_messages"}:
        return []

    await reset_daily_message_counts_if_needed()
    if limit is None:
        rows = await db_fetch(
            f"""
            SELECT user_id, {column}
            FROM message_stats
            WHERE guild_id = $1 AND {column} > 0
            ORDER BY {column} DESC, user_id ASC
            """,
            guild_id,
        )
    else:
        rows = await db_fetch(
            f"""
            SELECT user_id, {column}
            FROM message_stats
            WHERE guild_id = $1 AND {column} > 0
            ORDER BY {column} DESC, user_id ASC
            LIMIT $2
            """,
            guild_id,
            limit,
        )
    return [(row["user_id"], row[column]) for row in rows]


async def blacklist_message_channel(guild_id, channel_id):
    await db_execute(
        """
        INSERT INTO message_blacklist (guild_id, channel_id)
        VALUES ($1, $2)
        ON CONFLICT (guild_id, channel_id) DO NOTHING
        """,
        guild_id,
        channel_id,
        log_context=f"Blacklisted message channel: {channel_id}",
    )


async def unblacklist_message_channel(guild_id, channel_id):
    await db_execute(
        "DELETE FROM message_blacklist WHERE guild_id = $1 AND channel_id = $2",
        guild_id,
        channel_id,
        log_context=f"Unblacklisted message channel: {channel_id}",
    )


async def get_blacklisted_channels(guild_id):
    rows = await db_fetch(
        "SELECT channel_id FROM message_blacklist WHERE guild_id = $1 ORDER BY channel_id",
        guild_id,
    )
    return [row["channel_id"] for row in rows]


async def is_message_channel_blacklisted(guild_id, channel_id):
    return bool(
        await db_fetchval(
            "SELECT 1 FROM message_blacklist WHERE guild_id = $1 AND channel_id = $2",
            guild_id,
            channel_id,
        )
    )


def build_messages_embed(ctx, title, description):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_str("#2b2d31")
    )
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    return embed


def build_messages_usage_embed(ctx, command_name, usage):
    return build_messages_embed(
        ctx,
        "Missing required argument(s).",
        f"Usage: `.{command_name} {usage}`"
    )


def build_moderation_embed(ctx, title, description, success=True):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green() if success else discord.Color.red(),
    )
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    return embed


def build_automation_embed(ctx, title, description, success=True):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_str("#2b2d31") if success else discord.Color.red(),
    )
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    return embed


def build_asset_embed(title, description, success=True):
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_str("#2b2d31") if success else discord.Color.red(),
    )


def can_manage_guild_assets(member):
    permissions = getattr(member, "guild_permissions", None)
    if permissions is None:
        return False
    return bool(
        permissions.administrator
        or getattr(permissions, "manage_emojis_and_stickers", False)
        or getattr(permissions, "manage_expressions", False)
    )


def sanitize_asset_name(name, fallback="stolen_asset"):
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", name or "")
    if not cleaned:
        cleaned = fallback
    return cleaned[:32]


def extract_custom_emoji_asset(message):
    match = re.search(r"<(a?):([A-Za-z0-9_]+):(\d+)>", message.content)
    if not match:
        return None

    animated = bool(match.group(1))
    name = sanitize_asset_name(match.group(2), "stolen_emoji")
    emoji_id = int(match.group(3))
    partial = discord.PartialEmoji(name=name, animated=animated, id=emoji_id)
    extension = "gif" if animated else "png"
    return {
        "kind": "emoji",
        "name": name,
        "url": str(partial.url),
        "filename": f"{name}.{extension}",
    }


def extract_sticker_asset(message):
    if not message.stickers:
        return None

    sticker = message.stickers[0]
    sticker_format = getattr(sticker.format, "name", "").lower()
    if sticker_format == "lottie":
        extension = "json"
    elif sticker_format == "gif":
        extension = "gif"
    else:
        extension = "png"

    return {
        "kind": "sticker",
        "name": sanitize_asset_name(sticker.name, "stolen_sticker"),
        "url": str(sticker.url),
        "filename": f"{sanitize_asset_name(sticker.name, 'stolen_sticker')}.{extension}",
    }


async def download_asset_bytes(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError("Failed to download asset.")
            return await response.read()


class StealAssetView(discord.ui.View):
    def __init__(self, author_id, asset_data):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.asset_data = asset_data

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "Only the command author can use these buttons.", success=False),
                ephemeral=True,
            )
            return False
        return True

    async def _add_as_emoji(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "This action only works in a server.", success=False),
                ephemeral=True,
            )
            return

        if len(guild.emojis) >= guild.emoji_limit:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "❌ Emoji slots are full.", success=False),
                ephemeral=True,
            )
            return

        try:
            asset_bytes = await download_asset_bytes(self.asset_data["url"])
            await guild.create_custom_emoji(
                name=sanitize_asset_name(self.asset_data["name"], "stolen_emoji"),
                image=asset_bytes,
                reason=f"Asset stolen by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "Missing permission to add emojis.", success=False),
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            message = "Could not add that asset as an emoji."
            if "maximum" in str(e).lower() or "size" in str(e).lower():
                message = "File is too large for an emoji."
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", message, success=False),
                ephemeral=True,
            )
            return
        except Exception:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "Could not add that asset as an emoji.", success=False),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=build_asset_embed("Steal Asset", "✅ Emoji added successfully."),
            ephemeral=True,
        )
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()

    async def _add_as_sticker(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "This action only works in a server.", success=False),
                ephemeral=True,
            )
            return

        if len(guild.stickers) >= guild.sticker_limit:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "❌ Sticker slots are full.", success=False),
                ephemeral=True,
            )
            return

        try:
            asset_bytes = await download_asset_bytes(self.asset_data["url"])
            asset_file = discord.File(io.BytesIO(asset_bytes), filename=self.asset_data["filename"])
            await guild.create_sticker(
                name=sanitize_asset_name(self.asset_data["name"], "stolen_sticker"),
                description="Stolen asset",
                emoji="🙂",
                file=asset_file,
                reason=f"Asset stolen by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "Missing permission to add stickers.", success=False),
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            message = "Could not add that asset as a sticker."
            error_text = str(e).lower()
            if "size" in error_text or "maximum" in error_text:
                message = "File is too large for a sticker."
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", message, success=False),
                ephemeral=True,
            )
            return
        except Exception:
            await interaction.response.send_message(
                embed=build_asset_embed("Steal Asset", "Could not add that asset as a sticker.", success=False),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=build_asset_embed("Steal Asset", "✅ Sticker added successfully."),
            ephemeral=True,
        )
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()

    @discord.ui.button(label="Add as Emoji", style=discord.ButtonStyle.secondary)
    async def add_as_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._add_as_emoji(interaction)

    @discord.ui.button(label="Add as Sticker", style=discord.ButtonStyle.secondary)
    async def add_as_sticker(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._add_as_sticker(interaction)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            await interaction.response.defer()
        else:
            if not interaction.response.is_done():
                await interaction.response.defer()


async def set_guild_prefix(guild_id, prefix):
    await db_execute(
        """
        INSERT INTO guild_settings (guild_id, prefix)
        VALUES ($1, $2)
        ON CONFLICT (guild_id)
        DO UPDATE SET prefix = EXCLUDED.prefix
        """,
        guild_id,
        prefix,
        log_context=f"Saved guild prefix for guild: {guild_id}",
    )
    guild_prefix_cache[guild_id] = prefix


async def delete_guild_prefix(guild_id):
    await db_execute("DELETE FROM guild_settings WHERE guild_id = $1", guild_id, log_context=f"Deleted guild prefix for guild: {guild_id}")
    guild_prefix_cache.pop(guild_id, None)


async def get_guild_prefix(guild_id):
    if db is None:
        return DEFAULT_PREFIX

    return (
        await db_fetchval(
            "SELECT prefix FROM guild_settings WHERE guild_id = $1",
            guild_id,
        )
        or DEFAULT_PREFIX
    )


def format_relative_duration(from_dt):
    delta = datetime.now(timezone.utc) - from_dt
    total_seconds = max(int(delta.total_seconds()), 0)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts[:3])


def parse_short_duration(duration_text):
    duration_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        amount = int(duration_text[:-1])
        unit = duration_text[-1].lower()
        if amount <= 0 or unit not in duration_map:
            return None
        return amount * duration_map[unit]
    except (ValueError, IndexError):
        return None


class MemberOrID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            return await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            pass

        if ctx.guild and argument.isdigit():
            member_id = int(argument)
            member = ctx.guild.get_member(member_id)
            if member is not None:
                return member
            try:
                return await ctx.guild.fetch_member(member_id)
            except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                pass

        raise commands.MemberNotFound(argument)


def log_moderation_action(guild_id, action, moderator, target, reason=""):
    """Log moderation actions"""
    entry = {
        "action": action,
        "moderator": str(moderator),
        "target": str(target),
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    moderation_logs[guild_id].append(entry)

async def cache_server_invites(guild):
    """Cache all invites for a server"""
    try:
        invites = await guild.invites()
        server_invites[guild.id] = {invite.code: invite for invite in invites}
        print(f"✅ Cached {len(invites)} invites for {guild.name}")
    except discord.Forbidden:
        print(f"⚠️ No permission to view invites in {guild.name}")

def check_spam(user_id):
    """Check if user is spamming"""
    now = datetime.now(timezone.utc)
    recent = [t for t in spam_tracker[user_id] if (now - t).total_seconds() < SPAM_WINDOW]
    spam_tracker[user_id] = recent
    return len(recent) >= SPAM_THRESHOLD

responses = [
    "bhai chill kar \U0001f602",
    "itna gussa kyu \U0001f62d",
    "language control bro \U0001f624",
    "cool banne ki koshish fail \U0001f480",
    "admin bulaun kya \U0001f440",
]

afk_users = {}
MAX_AFK_PINGS_TO_SHOW = 5


def afk_cache_key(guild_id, user_id):
    return (guild_id, user_id)


def strip_afk_prefix(name):
    if not name:
        return name
    return name[6:] if name.startswith("[AFK] ") else name


def cache_afk_state(guild_id, user_id, reason, timestamp, pings=None):
    afk_users[afk_cache_key(guild_id, user_id)] = {
        "since": datetime.fromtimestamp(timestamp, tz=timezone.utc),
        "pings": list(pings or []),
        "reason": reason,
    }
    return afk_users[afk_cache_key(guild_id, user_id)]


async def save_afk_state(guild_id, user_id, reason, timestamp):
    await db_execute(
        """
        INSERT INTO afk_users (guild_id, user_id, reason, timestamp)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (guild_id, user_id)
        DO UPDATE SET
            reason = EXCLUDED.reason,
            timestamp = EXCLUDED.timestamp
        """,
        guild_id,
        user_id,
        reason,
        timestamp,
        log_context=f"Saved AFK state for user: {user_id}",
    )
    return cache_afk_state(guild_id, user_id, reason, timestamp)


async def get_afk_state(guild_id, user_id):
    key = afk_cache_key(guild_id, user_id)
    if key in afk_users:
        return afk_users[key]

    row = await db_fetchrow(
        "SELECT reason, timestamp FROM afk_users WHERE guild_id = $1 AND user_id = $2",
        guild_id,
        user_id,
    )
    if not row:
        return None
    return cache_afk_state(guild_id, user_id, row["reason"], row["timestamp"])


async def delete_afk_state(guild_id, user_id):
    afk_users.pop(afk_cache_key(guild_id, user_id), None)
    await db_execute(
        "DELETE FROM afk_users WHERE guild_id = $1 AND user_id = $2",
        guild_id,
        user_id,
        log_context=f"Deleted AFK state for user: {user_id}",
    )


async def load_afk_users():
    afk_users.clear()
    rows = await db_fetch("SELECT guild_id, user_id, reason, timestamp FROM afk_users")
    for row in rows:
        cache_afk_state(row["guild_id"], row["user_id"], row["reason"], row["timestamp"])


def format_duration(started_at):
    total_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())
    total_seconds = max(total_seconds, 0)

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return ", ".join(parts[:2])


def format_afk_reason(reason):
    if not reason:
        return ""

    return f"\nReason: {reason}"


def format_afk_pings(pings):
    if not pings:
        return "Nobody pinged you while you were AFK."

    shown_pings = pings[-MAX_AFK_PINGS_TO_SHOW:]
    lines = ["You were pinged by:"]

    for index, ping in enumerate(shown_pings, start=1):
        lines.append(f"{index}. {ping['by']} - {ping['url']}")

    hidden_count = len(pings) - len(shown_pings)
    if hidden_count:
        lines.append(f"And {hidden_count} older ping{'s' if hidden_count != 1 else ''}.")

    return "\n".join(lines)


# ===== TICKET SYSTEM VIEWS =====

class TicketCreateView(discord.ui.View):
    """View to create new tickets"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.green, emoji="🎫")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # Check for existing ticket by this user
        for channel_id, ticket_info in tickets.items():
            if ticket_info["creator"] == interaction.user.id:
                channel = bot.get_channel(channel_id)
                if channel:
                    await interaction.followup.send(
                        f"You already have an open ticket: {channel.mention}",
                        ephemeral=True
                    )
                    return

        # Create ticket channel
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        channel_name = f"ticket-{interaction.user.name}-{interaction.user.id % 10000}"
        ticket_channel = await guild.create_text_channel(
            channel_name,
            category=category,
            reason=f"Ticket created by {interaction.user}"
        )

        # Set permissions
        await ticket_channel.set_permissions(
            interaction.user,
            read_messages=True,
            send_messages=True
        )
        await ticket_channel.set_permissions(
            guild.default_role,
            read_messages=False
        )

        # Store ticket info
        tickets[ticket_channel.id] = {
            "creator": interaction.user.id,
            "created_at": datetime.now(timezone.utc)
        }

        # Send ticket message
        embed = discord.Embed(
            title="Support Ticket Created",
            description=f"Thank you for creating a ticket, {interaction.user.mention}!\n\nOur support team will help you shortly.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Click Close to close this ticket")

        await ticket_channel.send(
            embed=embed,
            view=TicketCloseView()
        )

        await interaction.followup.send(
            f"✅ Ticket created: {ticket_channel.mention}",
            ephemeral=True
        )


class TicketCloseView(discord.ui.View):
    """View to close tickets"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, emoji="❌")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel_id not in tickets:
            await interaction.response.send_message("This is not a valid ticket.", ephemeral=True)
            return

        ticket_info = tickets[interaction.channel_id]
        creator = interaction.guild.get_member(ticket_info["creator"])

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"This ticket has been closed by {interaction.user.mention}",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)
        
        # Delete after 5 seconds
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        tickets.pop(interaction.channel_id, None)


def build_ticket_embed(title, description, footer=None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_str("#2b2d31")
    )
    if footer:
        footer_icon = bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None
        embed.set_footer(text=footer, icon_url=footer_icon)
    return embed


def ticket_channel_name_for(user):
    safe_name = re.sub(r"[^a-z0-9-]", "", user.name.lower().replace(" ", "-"))[:70] or f"user-{user.id}"
    return f"ticket-{safe_name}"


def get_ticket_owner_id(channel):
    if not channel or not channel.topic or not channel.topic.startswith("ticket_owner_id:"):
        return None
    try:
        return int(channel.topic.split(":", 1)[1])
    except ValueError:
        return None


async def find_existing_ticket_channel(guild, user_id):
    for category_id in (TICKET_SUPPORT_CATEGORY_ID, TICKET_REWARDS_CATEGORY_ID):
        category = guild.get_channel(category_id)
        if category is None:
            continue

        for channel in category.text_channels:
            if get_ticket_owner_id(channel) == user_id:
                return channel
    return None


def build_ticket_panel_embed():
    return build_ticket_embed(
        TICKET_PANEL_TITLE,
        "To create a ticket use the buttons below\n• Have patience after creating a ticket\n• Creating ticket for fun could result in punishments!",
        "whAlien - Ticket System"
    )


def build_ticket_panel_embed():
    return build_ticket_embed(
        TICKET_PANEL_TITLE,
        "To create a ticket use the buttons below 🙂\n\nHave patience after creating a ticket 🤍",
        "whAlien - Ticket System"
    )


async def send_ticket_panel(channel):
    return await send_or_update_ticket_panel(channel)


async def send_or_update_ticket_panel(channel):
    embed = build_ticket_panel_embed()
    view = TicketPanelView()
    stored_message_id = await get_state_value(TICKET_PANEL_MESSAGE_KEY)
    if stored_message_id:
        try:
            message = await channel.fetch_message(int(stored_message_id))
            await message.edit(embed=embed, view=view)
            return message
        except (ValueError, discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    try:
        async for message in channel.history(limit=10):
            if message.author.id == bot.user.id and message.embeds:
                if message.embeds[0].title == TICKET_PANEL_TITLE:
                    await message.edit(embed=embed, view=view)
                    await set_state_value(TICKET_PANEL_MESSAGE_KEY, str(message.id))
                    return message
    except (discord.Forbidden, discord.HTTPException):
        pass

    embed = build_ticket_embed(
        TICKET_PANEL_TITLE,
        "To create a ticket use the buttons below\n• Have patience after creating a ticket\n• Creating ticket for fun could result in punishments!",
        "whAlien - Ticket System"
    )
    embed = build_ticket_panel_embed()
    message = await channel.send(embed=embed, view=view)
    await set_state_value(TICKET_PANEL_MESSAGE_KEY, str(message.id))
    return message


async def ensure_ticket_panel():
    panel_channel = bot.get_channel(TICKET_PANEL_CHANNEL_ID)
    if panel_channel is None:
        try:
            panel_channel = await bot.fetch_channel(TICKET_PANEL_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    try:
        await send_or_update_ticket_panel(panel_channel)
    except (discord.Forbidden, discord.HTTPException):
        pass


class TicketPanelView(discord.ui.View):
    """Persistent ticket panel."""
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        now = datetime.now(timezone.utc)
        expires_at = ticket_button_cooldowns.get(interaction.user.id)
        if expires_at and now < expires_at:
            remaining = int((expires_at - now).total_seconds())
            await interaction.response.send_message(
                f"Please wait {remaining}s before creating another ticket.",
                ephemeral=True,
            )
            return False
        return True

    async def _create_ticket(self, interaction: discord.Interaction, category_id: int):
        if interaction.guild is None:
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        existing_channel = await find_existing_ticket_channel(interaction.guild, interaction.user.id)
        if existing_channel is not None:
            await interaction.response.send_message(f"Ticket created: {existing_channel.mention}", ephemeral=True)
            return

        await interaction.response.send_message("Checking permissions...", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.edit_original_response(content="Creating ticket...")
        await asyncio.sleep(1)

        category = interaction.guild.get_channel(category_id)
        if category is None:
            await interaction.edit_original_response(content="Ticket category not found.")
            return

        try:
            await category.set_permissions(
                interaction.guild.default_role,
                view_channel=False,
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.edit_original_response(content="I don't have permission to secure the ticket category.")
            return

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }

        for role in interaction.guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                )

        try:
            ticket_channel = await interaction.guild.create_text_channel(
                ticket_channel_name_for(interaction.user),
                category=category,
                topic=f"ticket_owner_id:{interaction.user.id}",
                overwrites=overwrites,
                reason=f"Ticket created by {interaction.user}"
            )
        except discord.Forbidden:
            await interaction.edit_original_response(content="I don't have permission to create tickets.")
            return
        except discord.HTTPException:
            await interaction.edit_original_response(content="I could not create the ticket.")
            return

        welcome_embed = build_ticket_embed(
            "Welcome",
            "Support will be with you shortly.\nTo close this press the close button"
        )
        try:
            await ticket_channel.set_permissions(
                interaction.guild.default_role,
                view_channel=False,
                send_messages=False,
                read_message_history=False,
            )
            await ticket_channel.send(
                content=interaction.user.mention,
                embed=welcome_embed,
                view=TicketCloseView()
            )
        except discord.Forbidden:
            await interaction.edit_original_response(content="I don't have permission to finish setting up the ticket.")
            return
        except discord.HTTPException:
            await interaction.edit_original_response(content="I could not finish setting up the ticket.")
            return

        ticket_button_cooldowns[interaction.user.id] = datetime.now(timezone.utc) + timedelta(seconds=TICKET_BUTTON_COOLDOWN_SECONDS)
        await interaction.edit_original_response(content=f"Ticket created: {ticket_channel.mention}")

    @discord.ui.button(label="Rewards", style=discord.ButtonStyle.success, emoji="✨", custom_id="ticket_rewards")
    async def rewards_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket(interaction, TICKET_REWARDS_CATEGORY_ID)

    @discord.ui.button(label="Staff", style=discord.ButtonStyle.primary, emoji="📩", custom_id="ticket_staff")
    async def staff_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket(interaction, TICKET_SUPPORT_CATEGORY_ID)

    @discord.ui.button(label="Support", style=discord.ButtonStyle.danger, emoji="🤝", custom_id="ticket_support")
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket(interaction, TICKET_SUPPORT_CATEGORY_ID)


class TicketCreateView(TicketPanelView):
    """Compatibility alias for the existing tickets command."""
    pass


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔴")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_id = get_ticket_owner_id(interaction.channel)
        if owner_id is None:
            await interaction.response.send_message("This is not a valid ticket.", ephemeral=True)
            return

        member = interaction.guild.get_member(owner_id)
        target = member or discord.Object(id=owner_id)

        try:
            await interaction.channel.set_permissions(
                target,
                view_channel=False,
                send_messages=False,
                read_message_history=False,
            )
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to close this ticket.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("I could not close this ticket.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=None,
            embed=build_ticket_embed("Ticket", f"Ticket closed by {interaction.user.mention}"),
            view=None
        )
        await interaction.channel.send(
            embed=build_ticket_embed("Support team ticket controls", ""),
            view=TicketStaffControlsView(owner_id)
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="⚫")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()


class TicketCloseView(discord.ui.View):
    """Close prompt for open tickets."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ticket_close_prompt")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if get_ticket_owner_id(interaction.channel) is None:
            await interaction.response.send_message("This is not a valid ticket.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Are you sure you want to close this ticket?",
            view=TicketCloseConfirmView()
        )


class TicketStaffControlsView(discord.ui.View):
    def __init__(self, owner_id=None):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only admins can use these controls.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Open", style=discord.ButtonStyle.secondary, emoji="🔓", custom_id="ticket_staff_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner_id = self.owner_id or get_ticket_owner_id(interaction.channel)
        if owner_id is None:
            await interaction.response.send_message("This is not a valid ticket.", ephemeral=True)
            return

        member = interaction.guild.get_member(owner_id)
        target = member or discord.Object(id=owner_id)

        try:
            await interaction.channel.set_permissions(
                target,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to reopen this ticket.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("I could not reopen this ticket.", ephemeral=True)
            return

        await interaction.response.send_message("Ticket reopened")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑", custom_id="ticket_staff_delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Deleting ticket...", ephemeral=True)
        try:
            await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to delete this ticket.", ephemeral=True)
        except discord.HTTPException:
            await interaction.followup.send("I could not delete this ticket.", ephemeral=True)


# ===== TEMP VC VIEWS =====

class TempVCControlView(discord.ui.View):
    """Controls for temporary voice channels"""
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the channel owner can use these controls.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Lock", style=discord.ButtonStyle.primary, emoji="🔒")
    async def lock_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.edit(user_limit=len(interaction.channel.members))
        await interaction.response.send_message("Channel locked!", ephemeral=True)

    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.primary, emoji="🔓")
    async def unlock_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.edit(user_limit=0)
        await interaction.response.send_message("Channel unlocked!", ephemeral=True)

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def rename_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenameChannelModal(interaction.channel))


class RenameChannelModal(discord.ui.Modal, title="Rename Voice Channel"):
    new_name = discord.ui.TextInput(label="New Channel Name", max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.channel.edit(name=self.new_name.value)
            await interaction.response.send_message(f"Channel renamed to **{self.new_name.value}**", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to rename the channel.", ephemeral=True)


async def set_afk(member, reason=None):
    display_name = member.display_name
    timestamp = int(datetime.now(timezone.utc).timestamp())

    if display_name.startswith("[AFK] "):
        afk_name = display_name
    else:
        afk_name = f"[AFK] {display_name}"

    await save_afk_state(member.guild.id, member.id, reason, timestamp)

    if member.id == member.guild.owner_id:
        return

    try:
        await member.edit(nick=afk_name[:32], reason="User set AFK")
    except (discord.Forbidden, discord.HTTPException):
        pass


async def remove_afk(member):
    afk_data = await get_afk_state(member.guild.id, member.id)
    if not afk_data:
        return None

    await delete_afk_state(member.guild.id, member.id)

    if member.id != member.guild.owner_id:
        try:
            new_nick = strip_afk_prefix(member.nick) if member.nick else None
            if new_nick != member.nick:
                await member.edit(nick=new_nick[:32] if new_nick else None, reason="User returned from AFK")
        except (discord.Forbidden, discord.HTTPException):
            pass

    return afk_data


def find_role(guild, role_name):
    role_name = role_name.strip().lower()

    for role in guild.roles:
        if role.name.lower() == role_name:
            return role

    return None


async def send_restart_notice():
    channel = bot.get_channel(STARTUP_NOTICE_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(STARTUP_NOTICE_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False

    mentions = " and ".join(f"<@{user_id}>" for user_id in STARTUP_NOTIFY_USER_IDS)
    message = (
        f"hi {mentions}\n"
        "bot is back online ✅"
    )

    try:
        await channel.send(message)
        return True
    except discord.HTTPException:
        return False


async def ensure_verified_role_media_access():
    for guild in bot.guilds:
        channel = guild.get_channel(MEDIA_ONLY_CHANNEL_ID)
        role = guild.get_role(VERIFIED_ROLE_ID)
        if channel is None or role is None:
            continue

        try:
            await channel.set_permissions(
                role,
                send_messages=True,
                view_channel=True,
                read_message_history=True,
            )
        except discord.Forbidden:
            print(f"Missing permissions to update media access in {guild.name}")
        except discord.HTTPException:
            print(f"Failed to update media access in {guild.name}")


async def sync_membership_roles_for_member(member):
    if member.bot:
        return

    verified_role = member.guild.get_role(VERIFIED_ROLE_ID)
    wizards_role = member.guild.get_role(WIZARDS_ROLE_ID)
    unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
    if verified_role is None or wizards_role is None or unverified_role is None:
        return

    has_verified = verified_role in member.roles
    has_wizards = wizards_role in member.roles
    has_unverified = unverified_role in member.roles

    roles_to_add = []
    roles_to_remove = []

    if has_verified and not has_wizards:
        roles_to_add.append(wizards_role)

    if has_verified or has_wizards:
        if has_unverified:
            roles_to_remove.append(unverified_role)
    elif not has_unverified:
        roles_to_add.append(unverified_role)

    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add, reason="Membership role sync")
        except discord.Forbidden:
            print(f"Missing permissions to assign membership roles for {member}")
        except discord.HTTPException:
            print(f"Failed to assign membership roles for {member}")

    if roles_to_remove:
        try:
            await member.remove_roles(*roles_to_remove, reason="Membership role sync")
        except discord.Forbidden:
            print(f"Missing permissions to remove membership roles for {member}")
        except discord.HTTPException:
            print(f"Failed to remove membership roles for {member}")


async def sync_membership_roles_for_all_guilds():
    for guild in bot.guilds:
        for member in guild.members:
            await sync_membership_roles_for_member(member)


async def apply_membership_channel_access(guild):
    wizards_role = guild.get_role(WIZARDS_ROLE_ID)
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    if wizards_role is None or unverified_role is None:
        return

    onboarding_category = guild.get_channel(ONBOARDING_CATEGORY_ID)
    if isinstance(onboarding_category, discord.CategoryChannel):
        try:
            await onboarding_category.set_permissions(
                unverified_role,
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )
            await onboarding_category.set_permissions(
                wizards_role,
                view_channel=False,
            )
        except discord.Forbidden:
            print(f"Missing permissions to update onboarding category access in {guild.name}")
        except discord.HTTPException:
            print(f"Failed to update onboarding category access in {guild.name}")

    for channel_id in (CHANT_TO_START_CHANNEL_ID, SECURITY_VERIFICATION_CHANNEL_ID):
        channel = guild.get_channel(channel_id)
        if channel is None:
            continue

        allow_send = channel.id == CHANT_TO_START_CHANNEL_ID
        try:
            await channel.set_permissions(
                unverified_role,
                view_channel=True,
                send_messages=allow_send,
                read_message_history=True,
            )
            await channel.set_permissions(
                wizards_role,
                view_channel=False,
            )
        except discord.Forbidden:
            print(f"Missing permissions to update onboarding channel access in {guild.name}")
        except discord.HTTPException:
            print(f"Failed to update onboarding channel access in {guild.name}")

    for channel in guild.channels:
        if channel.id in {ONBOARDING_CATEGORY_ID, CHANT_TO_START_CHANNEL_ID, SECURITY_VERIFICATION_CHANNEL_ID}:
            continue

        channel_category_id = getattr(channel, "category_id", None)
        wizard_can_view = (
            channel.id not in BLOCKED_WIZARDS_CATEGORY_IDS
            and channel_category_id not in BLOCKED_WIZARDS_CATEGORY_IDS
        )

        try:
            await channel.set_permissions(unverified_role, view_channel=False)
            await channel.set_permissions(wizards_role, view_channel=wizard_can_view)
        except discord.Forbidden:
            print(f"Missing permissions to update membership access for {channel} in {guild.name}")
        except discord.HTTPException:
            print(f"Failed to update membership access for {channel} in {guild.name}")


async def apply_membership_channel_access_for_all_guilds():
    for guild in bot.guilds:
        await apply_membership_channel_access(guild)


async def ensure_verified_bonus_role(member):
    if member.bot:
        return

    verified_role = member.guild.get_role(VERIFIED_ROLE_ID)
    bonus_role = member.guild.get_role(VERIFIED_BONUS_ROLE_ID)
    if verified_role is None or bonus_role is None:
        return

    if verified_role not in member.roles or bonus_role in member.roles:
        return

    try:
        await member.add_roles(
            bonus_role,
            reason="Auto-assigned because member has the verified role",
        )
    except discord.Forbidden:
        print(f"Missing permissions to assign verified bonus role for {member}")
    except discord.HTTPException:
        print(f"Failed to assign verified bonus role for {member}")


async def sync_verified_bonus_roles():
    for guild in bot.guilds:
        verified_role = guild.get_role(VERIFIED_ROLE_ID)
        bonus_role = guild.get_role(VERIFIED_BONUS_ROLE_ID)
        if verified_role is None or bonus_role is None:
            continue

        for member in verified_role.members:
            if bonus_role not in member.roles:
                await ensure_verified_bonus_role(member)


async def ensure_birthday_role_visible():
    for guild in bot.guilds:
        birthday_role = guild.get_role(BIRTHDAY_ROLE_ID)
        if birthday_role is None or birthday_role.hoist:
            continue

        try:
            await birthday_role.edit(
                hoist=True,
                reason="Ensure birthday role stays visible on birthday",
            )
        except discord.Forbidden:
            print(f"Missing permissions to update birthday role display in {guild.name}")
        except discord.HTTPException:
            print(f"Failed to update birthday role display in {guild.name}")


async def sync_birthday_roles():
    today = get_ist_today()
    rows = await get_birthdays_for_day(today.month, today.day)
    birthdays_by_guild = defaultdict(set)

    for row in rows:
        birthdays_by_guild[row["guild_id"]].add(row["user_id"])

    for guild in bot.guilds:
        birthday_role = guild.get_role(BIRTHDAY_ROLE_ID)
        if birthday_role is None:
            continue

        should_have_role = birthdays_by_guild.get(guild.id, set())

        for member in list(birthday_role.members):
            if member.id in should_have_role:
                continue

            try:
                await member.remove_roles(
                    birthday_role,
                    reason="Birthday role removed because the birthday ended",
                )
            except discord.Forbidden:
                print(f"Missing permissions to remove birthday role for {member}")
            except discord.HTTPException:
                print(f"Failed to remove birthday role for {member}")

        for user_id in should_have_role:
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue

            if birthday_role in member.roles or member.bot:
                continue

            try:
                await member.add_roles(
                    birthday_role,
                    reason="Birthday role assigned for today's birthday",
                )
            except discord.Forbidden:
                print(f"Missing permissions to assign birthday role for {member}")
            except discord.HTTPException:
                print(f"Failed to assign birthday role for {member}")


async def sync_permission_roles_for_member(member):
    if member.bot:
        return

    links = await get_effective_permission_role_links(member.guild.id)
    if not links:
        return

    source_role_ids = {role.id for role in member.roles}
    managed_target_ids = {row["target_role_id"] for row in links}
    desired_target_ids = {
        row["target_role_id"]
        for row in links
        if row["source_role_id"] in source_role_ids
    }

    roles_to_add = []
    roles_to_remove = []

    for target_role_id in managed_target_ids:
        target_role = member.guild.get_role(target_role_id)
        if target_role is None:
            continue

        has_target_role = target_role in member.roles
        should_have_target_role = target_role_id in desired_target_ids

        if should_have_target_role and not has_target_role:
            roles_to_add.append(target_role)
        elif not should_have_target_role and has_target_role:
            roles_to_remove.append(target_role)

    if roles_to_add:
        try:
            await member.add_roles(
                *roles_to_add,
                reason="Auto-assigned permission bundle roles from source roles",
            )
        except discord.Forbidden:
            print(f"Missing permissions to assign permission bundle roles for {member}")
        except discord.HTTPException:
            print(f"Failed to assign permission bundle roles for {member}")

    if roles_to_remove:
        try:
            await member.remove_roles(
                *roles_to_remove,
                reason="Removed permission bundle roles because source roles no longer match",
            )
        except discord.Forbidden:
            print(f"Missing permissions to remove permission bundle roles for {member}")
        except discord.HTTPException:
            print(f"Failed to remove permission bundle roles for {member}")


async def sync_permission_roles_for_guild(guild):
    links = await get_effective_permission_role_links(guild.id)
    if not links:
        return

    for member in guild.members:
        await sync_permission_roles_for_member(member)


async def sync_permission_roles_for_all_guilds():
    for guild in bot.guilds:
        await sync_permission_roles_for_guild(guild)


async def handle_role_toggle(message):
    if not message.guild:
        await message.channel.send("Role changes only work inside a server.")
        return

    if not message.author.guild_permissions.administrator:
        await message.channel.send("Only admins can use this role command.")
        return

    if not message.mentions:
        await message.channel.send("Use it like: `role @user Role Name`")
        return

    member = message.mentions[0]
    parts = message.content.split(maxsplit=2)

    if len(parts) < 3:
        await message.channel.send("Use it like: `role @user Role Name`")
        return

    role_text = parts[2].strip()
    role = message.role_mentions[0] if message.role_mentions else find_role(message.guild, role_text)

    if role is None:
        await message.channel.send(f"I could not find a role named `{role_text}`.")
        return

    if role == message.guild.default_role:
        await message.channel.send("I cannot add or remove the everyone role.")
        return

    if role.managed:
        await message.channel.send("I cannot manage that role because it is controlled by an integration.")
        return

    if not message.guild.me.guild_permissions.manage_roles:
        await message.channel.send("I need Manage Roles permission before I can do that.")
        return

    if role >= message.guild.me.top_role:
        await message.channel.send("My role needs to be above that role before I can manage it.")
        return

    if message.author != message.guild.owner and role >= message.author.top_role:
        await message.channel.send("You can only manage roles below your highest role.")
        return

    try:
        if role in member.roles:
            await member.remove_roles(role, reason=f"Role toggled by {message.author}")
            await message.channel.send(
                f"Removed **{role.name}** from **{member.display_name}**.",
                allowed_mentions=discord.AllowedMentions(roles=False, users=False),
            )
        else:
            await member.add_roles(role, reason=f"Role toggled by {message.author}")
            await message.channel.send(
                f"Added **{role.name}** to **{member.display_name}**.",
                allowed_mentions=discord.AllowedMentions(roles=False, users=False),
            )
    except discord.Forbidden:
        await message.channel.send("Discord blocked that role change. Check role order and permissions.")
    except discord.HTTPException:
        await message.channel.send("Could not change that role right now. Try again later.")


async def send_bot_info(ctx):
    support_url = os.getenv("SUPPORT_URL", "https://discord.com")
    embed = discord.Embed(color=discord.Color.from_str("#2b2d31"))
    
    # Author section with bot profile picture
    embed.set_author(
        name="whAlien ✨",
        icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None
    )
    
    # Thumbnail (box-style profile image on right)
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user.display_avatar else None)
    
    # Compact text block (original wording, tight spacing)
    embed.description = (
        "Hey, I'm whAlien\n\n"
        "**Server Prefix:** `.`\n"
        "**Get Started:** Run `.commands` to discover all features\n"
        f"**Support:** Having issues? Join our [Support Server]({support_url})"
    )
    
    # Compact banner image
    embed.set_image(url="https://cdn.discordapp.com/attachments/1379052516863381638/1496561395964317746/f45fe253-c350-4f1a-9936-799b368b86de.png")
    
    # Footer
    embed.set_footer(text="Powered by Guddu Mistri • Made with love by @_anuneet1x 🤍")
    
    await ctx.send(embed=embed, view=WhAlienInfoView())


class WhAlienInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        support_url = os.getenv("SUPPORT_URL", "https://discord.com")

        self.add_item(discord.ui.Button(
            label="Features", 
            style=discord.ButtonStyle.link, 
            url=support_url
        ))
        self.add_item(discord.ui.Button(
            label="Support Server", 
            style=discord.ButtonStyle.link, 
            url=support_url
        ))


class LunexaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        categories = [
            discord.SelectOption(label="Config", emoji="⚙️"),
            discord.SelectOption(label="Info", emoji="ℹ️"),
            discord.SelectOption(label="Owner", emoji="👑"),
            discord.SelectOption(label="Roles", emoji="➕"),
            discord.SelectOption(label="AFK", emoji="💤"),
            discord.SelectOption(label="Server", emoji="🖥️"),
        ]

        self.add_item(
            discord.ui.Select(
                placeholder="Select Main Category",
                options=categories,
                custom_id="lunexa_category",
            )
        )

    async def interaction_check(self, interaction):
        if interaction.data.get("custom_id") == "lunexa_category":
            category = interaction.data.get("values")[0]
            await interaction.response.defer()
            await interaction.followup.send(f"You selected: **{category}**", ephemeral=True)
        return True


async def send_lunexa_welcome(ctx):
    support_url = os.getenv("SUPPORT_URL", "https://discord.com")
    embed = discord.Embed(color=discord.Color.from_str("#2b2d31"))
    
    # Author section with bot profile picture
    embed.set_author(
        name="whAlien ✨",
        icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None
    )
    
    # Thumbnail (box-style profile image on right)
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user.display_avatar else None)
    
    # Compact text block (original wording, tight spacing)
    embed.description = (
        "Hey, I'm whAlien\n\n"
        "**Server Prefix:** `.`\n"
        "**Get Started:** Run `.commands` to discover all features\n"
        f"**Support:** Having issues? Join our [Support Server]({support_url})"
    )
    
    # Compact banner image
    embed.set_image(url="https://cdn.discordapp.com/attachments/1379052516863381638/1496561395964317746/f45fe253-c350-4f1a-9936-799b368b86de.png")
    
    # Footer
    embed.set_footer(text="Powered by Guddu Mistri • Made with love by @_anuneet1x 🤍")
    
    await ctx.send(embed=embed, view=WhAlienInfoView())


def build_bot_info_embed():
    support_url = os.getenv("SUPPORT_URL", "https://discord.com")
    embed = discord.Embed(color=discord.Color.from_str("#2b2d31"))
    embed.set_author(
        name="whAlien ✨",
        icon_url=bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None)
    embed.description = (
        "Hey, I'm whAlien\n\n"
        f"**Prefix:** `{DEFAULT_PREFIX}`\n"
        f"**Servers:** `{len(bot.guilds)}`\n"
        f"**Support:** [Support Server]({support_url})"
    )
    embed.set_footer(text="Powered by whAlien")
    return embed


def build_giveaway_embed(prize, winners, duration_text, end_time, winner_text=None, ended=False):
    embed = discord.Embed(
        title="🎁 Giveaway",
        color=discord.Color.from_str("#2b2d31"),
        description=(
            f"Prize: {prize}\n"
            f"Winners: {winners}\n"
            f"Ends in: {duration_text}"
        ),
    )
    if ended:
        embed.description += f"\n\nWinner: {winner_text}"
    else:
        embed.description += f"\n\nEnds: {discord.utils.format_dt(end_time, style='R')}"
    embed.set_footer(text="React with 🎉 to enter")
    return embed


def build_giveaway_status_embed(title, description):
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_str("#2b2d31"),
    )


def get_giveaway_help_embed():
    return discord.Embed(
        title="Giveaway",
        color=discord.Color.from_str("#2b2d31"),
        description="""
Create giveaways in your Discord server

▶ `gstart <time> <winners> <prize>` - Create a giveaway
▶ `greroll` - Reroll a giveaway winner
▶ `gend` - End a giveaway early
        """
    )


def get_latest_giveaway(channel_id, active_only=False):
    channel_giveaways = [
        giveaway for giveaway in giveaways.values()
        if giveaway["channel_id"] == channel_id and (not active_only or not giveaway["ended"])
    ]
    if not channel_giveaways:
        return None
    return max(channel_giveaways, key=lambda giveaway: giveaway["message_id"])


async def resolve_giveaway_message(giveaway):
    channel = bot.get_channel(giveaway["channel_id"])
    if channel is None:
        try:
            channel = await bot.fetch_channel(giveaway["channel_id"])
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    try:
        return await channel.fetch_message(giveaway["message_id"])
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def pick_giveaway_winners(giveaway):
    message = await resolve_giveaway_message(giveaway)
    if message is None:
        return None, []

    reaction = discord.utils.get(message.reactions, emoji="🎉")
    if reaction is None:
        return message, []

    participants = []
    async for user in reaction.users():
        if user.bot:
            continue
        participants.append(user)

    unique_participants = list({user.id: user for user in participants}.values())
    if not unique_participants:
        return message, []

    winner_count = min(giveaway["winners"], len(unique_participants))
    return message, random.sample(unique_participants, winner_count)


async def finalize_giveaway(message_id, reroll=False):
    giveaway = giveaways.get(message_id)
    if giveaway is None:
        return False

    if giveaway["ended"] and not reroll:
        return False

    message, winners = await pick_giveaway_winners(giveaway)
    if message is None:
        giveaway["ended"] = True
        giveaway["task"] = None
        return False

    winner_text = ", ".join(winner.mention for winner in winners) if winners else "No valid participants"
    giveaway["ended"] = True
    giveaway["task"] = None

    try:
        await message.edit(
            embed=build_giveaway_embed(
                giveaway["prize"],
                giveaway["winners"],
                giveaway.get("duration_text", "Ended"),
                giveaway["end_time"],
                winner_text=winner_text,
                ended=True,
            )
        )
        await message.reply(
            f"Winner: {winner_text}" if winners else "Winner: No valid participants",
            mention_author=False,
        )
    except discord.HTTPException:
        return False

    return True


async def giveaway_timer(message_id, duration_seconds):
    await asyncio.sleep(duration_seconds)
    await finalize_giveaway(message_id)


class AFKConfirmView(discord.ui.View):
    def __init__(self, member, reason=None):
        super().__init__(timeout=30)
        self.member = member
        self.reason = reason

    async def interaction_check(self, interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "ye button tumhare liye nahi hai bro",
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm_afk(self, interaction, button):
        if self.member.id == self.member.guild.owner_id:
            await interaction.response.edit_message(
                content=f"{self.member.mention} you are the server owner, you can't set AFK!",
                view=None,
            )
            return

        try:
            await set_afk(self.member, self.reason)
        except discord.Forbidden:
            await interaction.response.edit_message(
                content="I need permission to manage nicknames before I can set AFK.",
                view=None,
            )
            return
        except discord.HTTPException:
            await interaction.response.edit_message(
                content="Could not change your nickname right now. Try again later.",
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=f"{self.member.mention} is now AFK.{format_afk_reason(self.reason)}",
            view=None,
        )

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def cancel_afk(self, interaction, button):
        await interaction.response.edit_message(
            content="AFK cancelled.",
            view=None,
        )


def format_invite_request_timestamp():
    return datetime.now().strftime("%d %b %Y %I:%M %p")


async def get_invite_ui_stats(guild_id, user_id):
    invites_count = await get_invites(guild_id, user_id)
    return {
        "invites": invites_count,
        "joins": invites_count,
        "leaves": 0,
        "fake": 0,
        "rejoins": 0,
    }


async def build_invites_embed(ctx, target):
    stats = await get_invite_ui_stats(ctx.guild.id, target.id)
    embed = discord.Embed(
        title="Invite log",
        color=INVITE_UI_COLOR,
        description=(
            f"> {target.display_name} has **{stats['invites']}** invites\n\n"
            f"Joins: **{stats['joins']}**\n"
            f"Left: **{stats['leaves']}**\n"
            f"Fake: **{stats['fake']}**\n"
            f"Rejoins: **{stats['rejoins']}** (7d)"
        ),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text=f"Requested by {ctx.author} • {format_invite_request_timestamp()}")
    return embed


class InvitedUsersView(discord.ui.View):
    def __init__(self, author_id, target, entries):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.target = target
        self.entries = entries
        self.page = 0
        self.message = None
        self._sync_buttons()

    @property
    def total_pages(self):
        return max(1, (len(self.entries) + INVITED_PAGE_SIZE - 1) // INVITED_PAGE_SIZE)

    def _sync_buttons(self, stopped=False):
        is_first_page = self.page == 0
        is_last_page = self.page >= self.total_pages - 1

        self.first_page.disabled = stopped or is_first_page
        self.previous_page.disabled = stopped or is_first_page
        self.stop_pages.disabled = stopped
        self.next_page.disabled = stopped or is_last_page
        self.last_page.disabled = stopped or is_last_page

    def build_embed(self):
        start = self.page * INVITED_PAGE_SIZE
        end = start + INVITED_PAGE_SIZE
        page_entries = self.entries[start:end]

        embed = discord.Embed(
            title=f"Invited list of {self.target.display_name} !",
            description="\n".join(
                f"#{index} • {entry}"
                for index, entry in enumerate(page_entries, start=start + 1)
            ),
            color=INVITE_UI_COLOR,
        )
        if not page_entries:
            embed.description = "No invited users found."
        embed.set_thumbnail(url=self.target.display_avatar.url)
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the command author can use these buttons.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        self._sync_buttons(stopped=True)
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._sync_buttons(stopped=True)
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.total_pages - 1, self.page + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self.total_pages - 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class LeaderboardView(discord.ui.View):
    def __init__(self, author_id, title, entries, intro_text=None):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.title = title
        self.entries = entries
        self.intro_text = intro_text
        self.page = 0
        self.message = None
        self._sync_buttons()

    @property
    def total_pages(self):
        return max(1, (len(self.entries) + LEADERBOARD_PAGE_SIZE - 1) // LEADERBOARD_PAGE_SIZE)

    def _sync_buttons(self, stopped=False):
        is_first_page = self.page == 0
        is_last_page = self.page >= self.total_pages - 1

        self.first_page.disabled = stopped or is_first_page
        self.previous_page.disabled = stopped or is_first_page
        self.stop_pages.disabled = stopped
        self.next_page.disabled = stopped or is_last_page
        self.last_page.disabled = stopped or is_last_page

    def build_embed(self):
        start = self.page * LEADERBOARD_PAGE_SIZE
        end = start + LEADERBOARD_PAGE_SIZE
        page_entries = self.entries[start:end]

        parts = []
        if self.intro_text:
            parts.append(self.intro_text)
        if page_entries:
            parts.append("\n".join(page_entries))

        embed = discord.Embed(
            title=self.title,
            description="\n\n".join(parts) if parts else "No data available.",
            color=discord.Color.from_str("#2b2d31")
        )
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the command author can use these buttons.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        self._sync_buttons(stopped=True)
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._sync_buttons(stopped=True)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
        self.stop()

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.total_pages - 1, self.page + 1)
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = self.total_pages - 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


@tasks.loop(seconds=7)
async def rotate_activity():
    """Rotate bot activity every 7 seconds"""
    global current_activity_index
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name=ACTIVITY_MESSAGES[current_activity_index]
    )
    await bot.change_presence(activity=activity)
    current_activity_index = (current_activity_index + 1) % len(ACTIVITY_MESSAGES)


@tasks.loop(minutes=5)
async def reset_daily_messages_loop():
    await reset_daily_message_counts_if_needed()


@tasks.loop(minutes=30)
async def birthday_role_sync_loop():
    await ensure_birthday_role_visible()
    await sync_birthday_roles()


@bot.event
async def on_ready():
    global startup_notice_sent
    print(f"Logged in as {bot.user}")
    
    # Initialize database
    await connect_db()
    await reset_daily_message_counts_if_needed()
    bot.add_view(TicketPanelView())
    bot.add_view(TicketCloseView())
    bot.add_view(TicketStaffControlsView())
    await ensure_ticket_panel()
    await ensure_verified_role_media_access()
    await apply_membership_channel_access_for_all_guilds()
    await sync_membership_roles_for_all_guilds()
    await sync_verified_bonus_roles()
    await ensure_birthday_role_visible()
    await sync_birthday_roles()
    await sync_base_roles_for_all_guilds()
    await sync_permission_roles_for_all_guilds()
    
    # Cache all server invites
    for guild in bot.guilds:
        await cache_server_invites(guild)
    
    # Start activity rotation if not already running
    if not rotate_activity.is_running():
        rotate_activity.start()

    if not reset_daily_messages_loop.is_running():
        reset_daily_messages_loop.start()

    if not birthday_role_sync_loop.is_running():
        birthday_role_sync_loop.start()

    if not startup_notice_sent:
        startup_notice_sent = True
        await send_restart_notice()
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


# ===== MEMBER JOIN EVENT =====
@bot.event
async def on_member_join(member):
    """Handle member join and track invites"""
    guild = member.guild

    await sync_base_role_for_member(member)
    await sync_membership_roles_for_member(member)
    await ensure_verified_bonus_role(member)
    await sync_permission_roles_for_member(member)

    verification_channel = guild.get_channel(SECURITY_VERIFICATION_CHANNEL_ID)
    if verification_channel is not None:
        try:
            prompt_message = await verification_channel.send(
                f"{member.mention} verify here",
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )
            await asyncio.sleep(3)
            await prompt_message.delete()
        except discord.Forbidden:
            print(f"Missing permissions to send verification prompt in {guild.name}")
        except discord.HTTPException:
            print(f"Failed to send verification prompt in {guild.name}")

    # ===== INVITE TRACKING =====
    try:
        # Get current invites
        current_invites = await guild.invites()
        old_invites = server_invites.get(guild.id, {})
        
        # Find which invite was used
        used_invite = None
        for invite in current_invites:
            if invite.code not in old_invites or old_invites[invite.code].uses < invite.uses:
                used_invite = invite
                break
        
        # Update cached invites
        server_invites[guild.id] = {invite.code: invite for invite in current_invites}
        
        if used_invite and used_invite.inviter:
            # Update inviter stats
            inviter_id = used_invite.inviter.id
            
            # Update database
            await add_invites(guild.id, inviter_id, 1)
            await set_inviter(guild.id, member.id, inviter_id)
            
    except discord.Forbidden:
        pass
    except Exception as e:
        print(f"Error tracking invite for {member}: {e}")


@bot.event
async def on_member_update(before, after):
    if before.roles == after.roles:
        return

    await sync_membership_roles_for_member(after)
    await sync_base_role_for_member(after)
    await ensure_verified_bonus_role(after)
    await sync_permission_roles_for_member(after)


# ===== TEMP VC SYSTEM =====
@bot.event
async def on_voice_state_update(member, before, after):
    """Handle temp VC creation and VC role assignment"""
    if member.bot:
        return

    guild = member.guild

    # ===== TEMP VC AUTO-CREATE =====
    # Check if user joined a "Create Channel" voice channel
    CREATE_TEMP_VC_CHANNEL_ID = None  # Set this to your create channel ID
    if CREATE_TEMP_VC_CHANNEL_ID and after.channel and after.channel.id == CREATE_TEMP_VC_CHANNEL_ID:
        # Create temp VC
        category = discord.utils.get(guild.categories, name=TEMP_VC_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TEMP_VC_CATEGORY_NAME)

        temp_channel = await guild.create_voice_channel(
            f"{member.display_name}'s Channel",
            category=category,
            user_limit=0
        )

        # Set permissions - user can manage, others can view
        await temp_channel.set_permissions(member, manage_channel=True)

        # Move user to new channel
        await member.move_to(temp_channel)
        temp_vc_users[member.id] = temp_channel.id

        # Send control message in text channel
        text_channel = guild.text_channels[0]
        embed = discord.Embed(
            title="🎙️ Temporary Voice Channel Created",
            description=f"{member.mention} created a temporary voice channel.",
            color=discord.Color.blue()
        )
        await text_channel.send(embed=embed, view=TempVCControlView(member.id))

    # ===== DELETE EMPTY TEMP VC =====
    if before.channel and not after.channel:
        if member.id in temp_vc_users:
            channel_id = temp_vc_users[member.id]
            channel = guild.get_channel(channel_id)
            if channel and len(channel.members) == 0:
                await channel.delete(reason="Temporary VC is now empty")
                del temp_vc_users[member.id]

    # ===== VC ROLE ASSIGNMENT =====
    vc_role_id = 1494308340619284490
    vc_role = guild.get_role(vc_role_id)

    if not vc_role:
        return

    try:
        if before.channel is None and after.channel is not None:
            await member.add_roles(vc_role, reason="User joined voice channel")
        elif before.channel is not None and after.channel is None:
            await member.remove_roles(vc_role, reason="User left voice channel")
    except discord.Forbidden:
        print(f"Missing permissions to manage roles for {member}")
    except discord.HTTPException:
        print(f"Failed to update role for {member}")


@bot.command(name="about", aliases=["info"])
async def about_command(ctx):
    await send_bot_info(ctx)


@bot.command(name="botinfo")
async def botinfo_command(ctx):
    """Show bot information"""
    await ctx.send(embed=build_bot_info_embed())


@bot.command(name="ping")
async def ping_command(ctx):
    """Show bot latency"""
    embed = discord.Embed(
        title="Pong",
        description=f"Latency: **{round(bot.latency * 1000)}ms**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.command(name="support")
async def support_command(ctx):
    """Send support server link"""
    support_url = os.getenv("SUPPORT_URL", "https://discord.com")
    embed = discord.Embed(
        title="Support Server",
        description=f"Join here: {support_url}",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


@bot.command(name="steal")
async def steal_command(ctx):
    if not can_manage_guild_assets(ctx.author):
        await ctx.send(embed=build_asset_embed("Steal Asset", "Missing permissions for this command.", success=False))
        return

    if not ctx.guild:
        await ctx.send(embed=build_asset_embed("Steal Asset", "This command only works in a server.", success=False))
        return

    if not ctx.message.reference or not isinstance(ctx.message.reference.resolved, discord.Message):
        await ctx.send(embed=build_asset_embed("Steal Asset", "Reply to a message containing an emoji or sticker.", success=False))
        return

    replied_message = ctx.message.reference.resolved
    asset_data = extract_custom_emoji_asset(replied_message) or extract_sticker_asset(replied_message)
    if asset_data is None:
        await ctx.send(embed=build_asset_embed("Steal Asset", "Reply to a message containing an emoji or sticker.", success=False))
        return

    if not (
        ctx.guild.me.guild_permissions.administrator
        or getattr(ctx.guild.me.guild_permissions, "manage_emojis_and_stickers", False)
        or getattr(ctx.guild.me.guild_permissions, "manage_expressions", False)
    ):
        await ctx.send(embed=build_asset_embed("Steal Asset", "I need Manage Emojis & Stickers permission.", success=False))
        return

    embed = build_asset_embed("Steal Asset", "Choose what to do with this asset")
    await ctx.send(embed=embed, view=StealAssetView(ctx.author.id, asset_data))


@bot.command(name="invite")
async def invite_command(ctx):
    """Show bot invite link"""
    if not bot.user:
        await ctx.send("Bot user is not ready yet.")
        return

    permissions = discord.Permissions(
        manage_messages=True,
        manage_channels=True,
        manage_roles=True,
        moderate_members=True,
        kick_members=True,
        ban_members=True,
        view_audit_log=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_external_emojis=True,
        add_reactions=True,
        connect=True,
        speak=True,
        move_members=True,
        manage_webhooks=True,
    )
    invite_url = discord.utils.oauth_url(bot.user.id, permissions=permissions)
    embed = discord.Embed(
        title="Invite Bot",
        description=f"[Click here to invite the bot]({invite_url})",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


@bot.command(name="serverinfo", aliases=["si"])
async def serverinfo_command(ctx):
    """Show server details"""
    guild = ctx.guild
    if not guild:
        await ctx.send("This command can only be used in a server.")
        return

    color = discord.Color.from_rgb(35, 40, 45)
    owner_text = guild.owner.mention if guild.owner else "Unknown"
    created = (
        f"{discord.utils.format_dt(guild.created_at, 'R')} • "
        f"{discord.utils.format_dt(guild.created_at, 'F')}"
    )
    verification_level = str(guild.verification_level).replace("_", " ")

    embed = discord.Embed(
        description=f"📊 Server Information\n{guild.description or 'No description set.'}",
        color=color
    )
    embed.set_author(
        name=guild.name,
        icon_url=guild.icon.url if guild.icon else None
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="📜 General Info",
        value=(
            f"Name: {guild.name}\n"
            f"Server ID: {guild.id}\n"
            f"Owner: {owner_text}\n"
            f"Created: {created}"
        ),
        inline=False
    )
    embed.add_field(
        name="👥 Members & Roles",
        value=(
            f"Members: {guild.member_count}\n"
            f"Roles: {len(guild.roles)}\n"
            f"Verification Level: {verification_level}"
        ),
        inline=True
    )
    embed.add_field(
        name="💎 Boost Status",
        value=(
            f"Level: {guild.premium_tier}\n"
            f"Boosts: {guild.premium_subscription_count}\n"
            f"AFK Timeout: {guild.afk_timeout} sec"
        ),
        inline=True
    )
    embed.add_field(
        name="📁 Channels",
        value=(
            f"Text: {len(guild.text_channels)}\n"
            f"Voice: {len(guild.voice_channels)}\n"
            f"Categories: {len(guild.categories)}"
        ),
        inline=False
    )

    embed.set_footer(
        text=f"Requested by {ctx.author}",
        icon_url=ctx.author.display_avatar.url
    )
    await ctx.send(embed=embed)


@bot.command(name="userinfo")
async def userinfo_command(ctx, member: MemberOrID = None):
    """Show user info"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    target = member or ctx.author
    roles = [role.mention for role in reversed(target.roles[1:])]
    top_roles = ", ".join(roles[:10]) if roles else "No roles"

    embed = discord.Embed(
        title=f"{target} User Info",
        color=target.color if target.color != discord.Color.default() else discord.Color.blurple()
    )
    embed.add_field(name="ID", value=str(target.id), inline=True)
    embed.add_field(name="Joined", value=discord.utils.format_dt(target.joined_at, style="F") if target.joined_at else "Unknown", inline=True)
    embed.add_field(name="Created", value=discord.utils.format_dt(target.created_at, style="F"), inline=True)
    embed.add_field(name="Top Role", value=target.top_role.mention if target.top_role else "None", inline=True)
    embed.add_field(name="Roles", value=top_roles, inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="roleinfo")
async def roleinfo_command(ctx, *, role: discord.Role):
    """Show role info"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    embed = discord.Embed(
        title=f"{role.name} Role Info",
        color=role.color if role.color != discord.Color.default() else discord.Color.blurple()
    )
    embed.add_field(name="ID", value=str(role.id), inline=True)
    embed.add_field(name="Members", value=str(len(role.members)), inline=True)
    embed.add_field(name="Position", value=str(role.position), inline=True)
    embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
    embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
    embed.add_field(name="Created", value=discord.utils.format_dt(role.created_at, style="F"), inline=False)
    await ctx.send(embed=embed)


@bot.command(name="vcinfo")
async def vcinfo_command(ctx, channel: discord.VoiceChannel = None):
    """Show voice channel info"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    target_channel = channel
    if target_channel is None and isinstance(ctx.author, discord.Member) and ctx.author.voice:
        target_channel = ctx.author.voice.channel

    if target_channel is None:
        await ctx.send("Provide a voice channel or join one first.")
        return

    embed = discord.Embed(
        title=f"{target_channel.name} Voice Channel",
        color=discord.Color.blurple()
    )
    embed.add_field(name="ID", value=str(target_channel.id), inline=True)
    embed.add_field(name="Members", value=str(len(target_channel.members)), inline=True)
    embed.add_field(name="User Limit", value=str(target_channel.user_limit or "Unlimited"), inline=True)
    embed.add_field(name="Bitrate", value=f"{target_channel.bitrate // 1000} kbps", inline=True)
    embed.add_field(name="Category", value=target_channel.category.name if target_channel.category else "None", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="avatar", aliases=["av"])
async def avatar_command(ctx, member: MemberOrID = None):
    """Show user's avatar"""
    target = member or ctx.author
    embed = discord.Embed(
        title=f"{target} Avatar",
        color=discord.Color.blurple()
    )
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="banner")
async def banner_command(ctx, member: MemberOrID = None):
    """Show user's banner"""
    target = member or ctx.author
    try:
        user = await bot.fetch_user(target.id)
    except discord.HTTPException:
        await ctx.send("I could not fetch that user's banner right now.")
        return

    if not user.banner:
        await ctx.send("This user does not have a banner.")
        return

    embed = discord.Embed(
        title=f"{target} Banner",
        color=discord.Color.blurple()
    )
    embed.set_image(url=user.banner.url)
    await ctx.send(embed=embed)


@bot.command(name="guildbanner")
async def guildbanner_command(ctx):
    """Show server banner"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    if not ctx.guild.banner:
        await ctx.send("This server does not have a banner.")
        return

    embed = discord.Embed(
        title=f"{ctx.guild.name} Banner",
        color=discord.Color.blurple()
    )
    embed.set_image(url=ctx.guild.banner.url)
    await ctx.send(embed=embed)


@bot.command(name="membercount")
async def membercount_command(ctx):
    """Show total members count"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    embed = discord.Embed(
        title="Member Count",
        description=f"Total members: **{ctx.guild.member_count}**",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


@bot.command(name="shards")
async def shards_command(ctx):
    """Show shard info"""
    shard_id = ctx.guild.shard_id if ctx.guild and ctx.guild.shard_id is not None else 0
    shard_count = bot.shard_count or 1
    latency = round(bot.latency * 1000)

    embed = discord.Embed(
        title="Shard Info",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Shard", value=f"{shard_id + 1}/{shard_count}", inline=True)
    embed.add_field(name="Latency", value=f"{latency}ms", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="permissions")
async def permissions_command(ctx):
    """Show bot permissions in server"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    perms = ctx.channel.permissions_for(ctx.guild.me)
    enabled = []
    for name in [
        "send_messages", "embed_links", "attach_files", "manage_messages",
        "manage_channels", "manage_roles", "moderate_members", "view_audit_log"
    ]:
        if getattr(perms, name, False):
            enabled.append(name.replace("_", " ").title())

    embed = discord.Embed(
        title="Bot Permissions",
        description="\n".join(enabled) if enabled else "No notable permissions.",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


@bot.command(name="accountage")
async def accountage_command(ctx, member: MemberOrID = None):
    """Show account creation age"""
    target = member or ctx.author
    embed = discord.Embed(
        title="Account Age",
        description=(
            f"{target.mention} created their account on "
            f"**{target.created_at.strftime('%d %b %Y')}**\n"
            f"Age: **{format_relative_duration(target.created_at)}**"
        ),
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


@bot.command(name="uptime")
async def uptime_command(ctx):
    """Show bot uptime"""
    embed = discord.Embed(
        title="Uptime",
        description=f"Bot uptime: **{format_relative_duration(BOT_START_TIME)}**",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


@bot.command(name="setprefix")
@commands.has_permissions(administrator=True)
async def setprefix_command(ctx, *, new_prefix: str):
    """Change bot prefix"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    new_prefix = new_prefix.strip()
    if not new_prefix or len(new_prefix) > 5:
        await ctx.send("Prefix must be between 1 and 5 characters.")
        return

    await set_guild_prefix(ctx.guild.id, new_prefix)
    await ctx.send(embed=discord.Embed(
        title="Prefix Updated",
        description=f"New prefix: `{new_prefix}`",
        color=discord.Color.green()
    ))


@bot.command(name="deleteprefix")
@commands.has_permissions(administrator=True)
async def deleteprefix_command(ctx):
    """Reset prefix to default"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    await delete_guild_prefix(ctx.guild.id)
    await ctx.send(embed=discord.Embed(
        title="Prefix Reset",
        description=f"Prefix reset to `{DEFAULT_PREFIX}`",
        color=discord.Color.orange()
    ))


@bot.command(name="dbtest")
async def dbtest_command(ctx):
    """Temporary database verification command"""
    if db is None:
        await ctx.send("Database is not connected.")
        return

    test_key = f"dbtest:{ctx.guild.id if ctx.guild else 0}:{ctx.author.id}"
    test_value = f"ok:{int(datetime.now(timezone.utc).timestamp())}"
    await set_state_value(test_key, test_value)
    saved_value = await get_state_value(test_key)

    if saved_value == test_value:
        await ctx.send("Database working correctly")
        return

    await ctx.send("Database test failed")


@bot.command(name="gstart")
@commands.has_permissions(manage_guild=True)
async def gstart_command(ctx, duration: str, winners: int, *, prize: str):
    """Start a giveaway"""
    if winners <= 0:
        await ctx.send(embed=build_giveaway_status_embed(
            "Missing required argument(s).",
            "Invalid format. Example: `.gstart 1m 1 Nitro`"
        ))
        return

    duration_seconds = parse_short_duration(duration)
    if duration_seconds is None:
        await ctx.send(embed=build_giveaway_status_embed(
            "Missing required argument(s).",
            "Invalid format. Example: `.gstart 1m 1 Nitro`"
        ))
        return

    end_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    embed = build_giveaway_embed(prize, winners, duration, end_time)
    giveaway_message = await ctx.send(embed=embed)

    try:
        await giveaway_message.add_reaction("🎉")
    except discord.HTTPException:
        await ctx.send(embed=build_giveaway_status_embed(
            "Giveaway",
            "I could not add the giveaway reaction."
        ))
        return

    giveaway_task = asyncio.create_task(giveaway_timer(giveaway_message.id, duration_seconds))
    giveaways[giveaway_message.id] = {
        "message_id": giveaway_message.id,
        "channel_id": ctx.channel.id,
        "guild_id": ctx.guild.id if ctx.guild else None,
        "end_time": end_time,
        "winners": winners,
        "prize": prize,
        "duration_text": duration,
        "ended": False,
        "task": giveaway_task,
    }


@bot.command(name="gend")
@commands.has_permissions(manage_guild=True)
async def gend_command(ctx):
    """End an active giveaway early"""
    giveaway = get_latest_giveaway(ctx.channel.id, active_only=True)
    if giveaway is None:
        await ctx.send(embed=build_giveaway_status_embed(
            "Giveaway",
            "No active giveaway found in this channel."
        ))
        return

    if giveaway["task"] is not None:
        giveaway["task"].cancel()
        giveaway["task"] = None

    success = await finalize_giveaway(giveaway["message_id"])
    if not success:
        await ctx.send(embed=build_giveaway_status_embed(
            "Giveaway",
            "I could not end that giveaway. The message may have been deleted."
        ))
        return

    await ctx.send(embed=build_giveaway_status_embed(
        "Giveaway",
        "Giveaway ended."
    ))


@bot.command(name="greroll")
@commands.has_permissions(manage_guild=True)
async def greroll_command(ctx):
    """Reroll a giveaway winner"""
    giveaway = get_latest_giveaway(ctx.channel.id, active_only=False)
    if giveaway is None:
        await ctx.send(embed=build_giveaway_status_embed(
            "Giveaway",
            "No giveaway found in this channel."
        ))
        return

    if not giveaway["ended"]:
        await ctx.send(embed=build_giveaway_status_embed(
            "Giveaway",
            "That giveaway is still running. Use `.gend` first if you want to end it early."
        ))
        return

    success = await finalize_giveaway(giveaway["message_id"], reroll=True)
    if not success:
        await ctx.send(embed=build_giveaway_status_embed(
            "Giveaway",
            "I could not reroll that giveaway. The message may have been deleted."
        ))
        return

    await ctx.send(embed=build_giveaway_status_embed(
        "Giveaway",
        "Giveaway rerolled."
    ))


@gstart_command.error
async def gstart_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_giveaway_status_embed(
            "Missing required argument(s).",
            "Usage: `.gstart <time> <winners> <prize>`\nExample: `.gstart 1m 1 Nitro Classic`"
        ))
        return
    if isinstance(error, (commands.BadArgument, commands.TooManyArguments)):
        await ctx.send(embed=build_giveaway_status_embed(
            "Missing required argument(s).",
            "Invalid format. Example: `.gstart 1m 1 Nitro`"
        ))
        return
    raise error


@greroll_command.error
async def greroll_error(ctx, error):
    if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.TooManyArguments)):
        await ctx.send(embed=build_giveaway_status_embed(
            "Missing required argument(s).",
            "Usage: `.greroll`"
        ))
        return
    raise error


@gend_command.error
async def gend_error(ctx, error):
    if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.TooManyArguments)):
        await ctx.send(embed=build_giveaway_status_embed(
            "Missing required argument(s).",
            "Usage: `.gend`"
        ))
        return
    raise error


# ===== MODERATION COMMANDS =====

@bot.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def warn_command(ctx, member: MemberOrID, *, reason="No reason provided"):
    """Warn a member"""
    if member == ctx.author:
        await ctx.send(embed=build_moderation_embed(ctx, "Warning Failed", "You cannot warn yourself.", success=False))
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send(embed=build_moderation_embed(ctx, "Warning Failed", "You cannot warn someone with a higher or equal role.", success=False))
        return

    warnings[ctx.guild.id][member.id] += 1
    warn_count = warnings[ctx.guild.id][member.id]
    log_moderation_action(ctx.guild.id, "warn", ctx.author, member, reason)

    embed = discord.Embed(
        title="User Warned",
        description=f"Warned {member.mention}\nWarning Count: {warn_count}",
        color=discord.Color.green()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed)

    # Auto-mute after 3 warnings
    if warn_count >= 3:
        await mute_member(ctx, member, reason="Auto-mute: 3 warnings")


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute_command(ctx, member: MemberOrID, duration: str = "10m", *, reason="No reason provided"):
    """Mute a member (duration: 1m, 1h, 1d, etc.)"""
    await mute_member(ctx, member, duration, reason)


async def mute_member(ctx, member: discord.Member, duration: str = "10m", reason="No reason provided"):
    """Internal function to mute a member"""
    if member == ctx.author:
        await ctx.send(embed=build_moderation_embed(ctx, "Mute Failed", "You cannot mute yourself.", success=False))
        return

    # Parse duration
    duration_map = {"m": 60, "h": 3600, "d": 86400}
    try:
        num = int(duration[:-1])
        unit = duration[-1].lower()
        seconds = num * duration_map.get(unit, 60)
    except:
        seconds = 600  # Default 10 minutes

    mute_duration = timedelta(seconds=seconds)

    try:
        await member.timeout(mute_duration, reason=reason)
        log_moderation_action(ctx.guild.id, "mute", ctx.author, member, reason)
        embed = build_moderation_embed(ctx, "User Muted", f"Muted {member.mention} for {duration}")
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send(embed=build_moderation_embed(ctx, "Mute Failed", "I don't have permission to mute this member.", success=False))


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute_command(ctx, *, target: str):
    """Unmute a member or everyone currently timed out"""
    if target.lower() == "all":
        timed_out_members = [member for member in ctx.guild.members if member.is_timed_out()]
        if not timed_out_members:
            await ctx.send(embed=build_moderation_embed(ctx, "Unmute All", "No muted members found in this server.", success=False))
            return

        unmuted_count = 0
        failed_count = 0
        for member in timed_out_members:
            try:
                await member.timeout(None, reason=f"Mass unmute by {ctx.author}")
                log_moderation_action(ctx.guild.id, "unmute", ctx.author, member, "Mass unmute")
                unmuted_count += 1
            except discord.Forbidden:
                failed_count += 1

        description = f"Unmuted {unmuted_count} member(s)."
        if failed_count:
            description += f" Failed to unmute {failed_count} member(s)."
        await ctx.send(embed=build_moderation_embed(ctx, "Unmute All", description, success=unmuted_count > 0))
        return

    try:
        member = await MemberOrID().convert(ctx, target)
    except commands.MemberNotFound:
        await ctx.send(embed=build_moderation_embed(ctx, "Unmute Failed", "Member not found. Use `.unmute <@user | user_id | all>`.", success=False))
        return

    try:
        await member.timeout(None)
        log_moderation_action(ctx.guild.id, "unmute", ctx.author, member, "Manual unmute")
        await ctx.send(embed=build_moderation_embed(ctx, "User Unmuted", f"Unmuted {member.mention}"))
    except discord.Forbidden:
        await ctx.send(embed=build_moderation_embed(ctx, "Unmute Failed", "I don't have permission to unmute this member.", success=False))


@unmute_command.error
async def unmute_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_moderation_embed(ctx, "Missing required argument(s).", "Usage: `.unmute <@user | user_id | all>`", success=False))
        return
    raise error


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_command(ctx, member: MemberOrID, *, reason="No reason provided"):
    """Kick a member from the server"""
    if member == ctx.author:
        await ctx.send(embed=build_moderation_embed(ctx, "Kick Failed", "You cannot kick yourself.", success=False))
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send(embed=build_moderation_embed(ctx, "Kick Failed", "You cannot kick someone with a higher or equal role.", success=False))
        return

    try:
        await member.kick(reason=reason)
        log_moderation_action(ctx.guild.id, "kick", ctx.author, member, reason)
        embed = build_moderation_embed(ctx, "User Kicked", f"Kicked {member.mention}")
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send(embed=build_moderation_embed(ctx, "Kick Failed", "I don't have permission to kick this member.", success=False))


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_command(ctx, member: MemberOrID, *, reason="No reason provided"):
    """Ban a member from the server"""
    if member == ctx.author:
        await ctx.send(embed=build_moderation_embed(ctx, "Ban Failed", "You cannot ban yourself.", success=False))
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send(embed=build_moderation_embed(ctx, "Ban Failed", "You cannot ban someone with a higher or equal role.", success=False))
        return

    try:
        await member.ban(reason=reason)
        log_moderation_action(ctx.guild.id, "ban", ctx.author, member, reason)
        embed = build_moderation_embed(ctx, "User Banned", f"Banned {member}")
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send(embed=build_moderation_embed(ctx, "Ban Failed", "I don't have permission to ban this member.", success=False))


@bot.command(name="purge")
@commands.has_permissions(manage_messages=True)
async def purge_command(ctx, amount: int = 10):
    """Delete messages from the channel"""
    if amount < 1 or amount > 100:
        await ctx.send(embed=build_moderation_embed(ctx, "Purge Failed", "Please specify between 1 and 100 messages to delete.", success=False))
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(
            embed=build_moderation_embed(ctx, "Messages Purged", f"Deleted {len(deleted) - 1} messages."),
            delete_after=5,
        )
        log_moderation_action(ctx.guild.id, "purge", ctx.author, "system", f"Deleted {len(deleted) - 1} messages")
    except discord.Forbidden:
        await ctx.send(embed=build_moderation_embed(ctx, "Purge Failed", "I don't have permission to delete messages.", success=False))


@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode_command(ctx, seconds: int = 0):
    """Set slowmode for the channel (0 to disable)"""
    if seconds < 0 or seconds > 21600:
        await ctx.send(embed=build_moderation_embed(ctx, "Slowmode Failed", "Slowmode must be between 0 and 21600 seconds.", success=False))
        return

    try:
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(embed=build_moderation_embed(ctx, "Slowmode Updated", "Slowmode disabled."))
        else:
            await ctx.send(embed=build_moderation_embed(ctx, "Slowmode Updated", f"Slowmode set to {seconds} seconds."))
        log_moderation_action(ctx.guild.id, "slowmode", ctx.author, "channel", f"Set to {seconds}s")
    except discord.Forbidden:
        await ctx.send(embed=build_moderation_embed(ctx, "Slowmode Failed", "I don't have permission to modify this channel.", success=False))


@bot.group(name="autoresponder", invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def autoresponder_command(ctx):
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Autoresponder",
        "Usage: `.autoresponder <add | remove | show>`",
        success=False,
    ))


@autoresponder_command.command(name="add")
@commands.has_permissions(manage_guild=True)
async def autoresponder_add_command(ctx, trigger: str, *, response: str):
    await add_autoresponder(ctx.guild.id, trigger, response)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Autoresponder",
        f"Saved autoresponder for `{trigger.lower()}`.",
    ))


@autoresponder_command.command(name="remove")
@commands.has_permissions(manage_guild=True)
async def autoresponder_remove_command(ctx, *, trigger: str):
    await remove_autoresponder(ctx.guild.id, trigger)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Autoresponder",
        f"Removed autoresponder for `{trigger.lower()}`.",
    ))


@autoresponder_command.command(name="show")
@commands.has_permissions(manage_guild=True)
async def autoresponder_show_command(ctx):
    responders = await get_autoresponders(ctx.guild.id)
    if not responders:
        await ctx.send(embed=build_automation_embed(ctx, "Autoresponder", "No autoresponders configured."))
        return

    lines = [f"▶ `{trigger}` → {response}" for trigger, response in responders[:20]]
    await ctx.send(embed=build_automation_embed(ctx, "Autoresponder", "\n".join(lines)))


@bot.group(name="autoreact", invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def autoreact_command(ctx):
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Autoreact",
        "Usage: `.autoreact <add | remove | show>`",
        success=False,
    ))


@autoreact_command.command(name="add")
@commands.has_permissions(manage_guild=True)
async def autoreact_add_command(ctx, trigger: str, emoji: str):
    await add_auto_reaction(ctx.guild.id, trigger, emoji)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Autoreact",
        f"Saved auto reaction for `{trigger.lower()}`.",
    ))


@autoreact_command.command(name="remove")
@commands.has_permissions(manage_guild=True)
async def autoreact_remove_command(ctx, *, trigger: str):
    await remove_auto_reaction(ctx.guild.id, trigger)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Autoreact",
        f"Removed auto reaction for `{trigger.lower()}`.",
    ))


@autoreact_command.command(name="show")
@commands.has_permissions(manage_guild=True)
async def autoreact_show_command(ctx):
    reactions = await get_auto_reactions(ctx.guild.id)
    if not reactions:
        await ctx.send(embed=build_automation_embed(ctx, "Autoreact", "No auto reactions configured."))
        return

    lines = [f"▶ `{trigger}` → {emoji}" for trigger, emoji in reactions[:20]]
    await ctx.send(embed=build_automation_embed(ctx, "Autoreact", "\n".join(lines)))


@bot.group(name="sticky", invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def sticky_command(ctx):
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Sticky Message",
        "Usage: `.sticky <set | remove | show>`",
        success=False,
    ))


@sticky_command.command(name="set")
@commands.has_permissions(manage_guild=True)
async def sticky_set_command(ctx, *, message_text: str):
    await set_sticky_message(ctx.guild.id, message_text)
    await ctx.send(embed=build_automation_embed(ctx, "Sticky Message", "Sticky message saved."))


@sticky_command.command(name="remove")
@commands.has_permissions(manage_guild=True)
async def sticky_remove_command(ctx):
    await remove_sticky_message(ctx.guild.id)
    await ctx.send(embed=build_automation_embed(ctx, "Sticky Message", "Sticky message removed."))


@sticky_command.command(name="show")
@commands.has_permissions(manage_guild=True)
async def sticky_show_command(ctx):
    sticky_message = await get_sticky_message(ctx.guild.id)
    if not sticky_message:
        await ctx.send(embed=build_automation_embed(ctx, "Sticky Message", "No sticky message configured."))
        return

    await ctx.send(embed=build_automation_embed(ctx, "Sticky Message", sticky_message))


@autoresponder_add_command.error
@autoresponder_remove_command.error
@autoreact_add_command.error
@autoreact_remove_command.error
@sticky_set_command.error
async def automation_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Missing required argument(s).",
            "Check the command usage in the help menu.",
            success=False,
        ))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Invalid argument.",
            "Check the command usage in the help menu.",
            success=False,
        ))
        return
    raise error


@bot.command(name="tickets")
async def tickets_command(ctx):
    """Show ticket creation panel"""
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description="Click the button below to create a support ticket. Our team will assist you shortly.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=TicketCreateView())


@bot.command(name="sendtickets")
@commands.has_permissions(administrator=True)
async def sendtickets_command(ctx):
    """Send the ticket panel manually"""
    panel_channel = bot.get_channel(TICKET_PANEL_CHANNEL_ID)
    if panel_channel is None:
        try:
            panel_channel = await bot.fetch_channel(TICKET_PANEL_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await ctx.send(embed=build_ticket_embed("Support Ticket 🎟️", "Panel channel not found."))
            return

    try:
        message = await send_ticket_panel(panel_channel)
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send(embed=build_ticket_embed("Support Ticket 🎟️", "I could not send the ticket panel."))
        return

    await ctx.send(embed=build_ticket_embed("Support Ticket 🎟️", f"Ticket panel sent in {panel_channel.mention}.\nMessage ID: `{message.id}`"))


@bot.command(name="modlogs")
@commands.has_permissions(administrator=True)
async def modlogs_command(ctx, member: MemberOrID = None):
    """View moderation logs"""
    logs = moderation_logs.get(ctx.guild.id, [])
    
    if not logs:
        await ctx.send("No moderation logs found.")
        return

    if member:
        logs = [log for log in logs if log.get("target") == str(member)]

    if not logs:
        await ctx.send(f"No logs found for {member}.")
        return

    # Show last 10 logs
    embed = discord.Embed(
        title="📋 Moderation Logs",
        color=discord.Color.blue()
    )

    for log in logs[-10:]:
        action = log.get("action", "unknown").upper()
        moderator = log.get("moderator", "Unknown")
        reason = log.get("reason", "No reason")
        embed.add_field(
            name=f"{action} by {moderator}",
            value=reason,
            inline=False
        )

    await ctx.send(embed=embed)


# ===== INVITE TRACKING COMMANDS =====

@bot.command(name="invites", aliases=["inv", "i"])
async def invites_command(ctx, member: MemberOrID = None):
    """Show number of invites of a user"""
    target = member or ctx.author

    await ctx.send(embed=await build_invites_embed(ctx, target))


@bot.command(name="inviter")
async def inviter_command(ctx, member: MemberOrID = None):
    """Show who invited the user"""
    target = member or ctx.author
    
    inviter_id = await get_inviter(ctx.guild.id, target.id)
    if not inviter_id:
        await ctx.send(f"Could not find who invited {target.display_name}.")
        return
    
    try:
        inviter = await bot.fetch_user(inviter_id)
        embed = discord.Embed(
            title="👤 Who Invited",
            color=discord.Color.blurple()
        )
        embed.description = (
            f"{target.display_name} was invited by "
            f"{getattr(inviter, 'display_name', inviter.name)}"
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)
    except:
        await ctx.send(f"Could not find who invited {target.display_name}.")


@bot.command(name="invited")
async def invited_command(ctx, member: MemberOrID = None):
    """List users invited by someone"""
    target = member or ctx.author

    invited_users = await get_invited_users(ctx.guild.id, target.id)

    entries = []
    for uid in invited_users:
        try:
            user = ctx.guild.get_member(uid) or await bot.fetch_user(uid)
            entries.append(getattr(user, "display_name", user.name))
        except Exception:
            entries.append(f"User({uid})")

    view = InvitedUsersView(ctx.author.id, target, entries)
    if entries:
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message
        return

    await ctx.send(embed=view.build_embed())


@bot.command(name="inviteinfo")
async def inviteinfo_command(ctx, member: MemberOrID = None):
    """Show active invite links created by a user"""
    target = member or ctx.author
    try:
        invites = await ctx.guild.invites()
    except discord.Forbidden:
        await ctx.send("I don't have permission to view invites.")
        return

    user_invites = [
        invite for invite in invites
        if invite.inviter and invite.inviter.id == target.id
    ]

    embed = discord.Embed(
        title=f"Invite codes of {target.display_name} !",
        description=(
            "\n".join(
                f"Invite {invite.code} • {invite.uses} Uses"
                for invite in user_invites[:10]
            )
            if user_invites
            else "No active invites found."
        ),
        color=discord.Color.blurple()
    )

    await ctx.send(embed=embed)


@bot.command(name="addinvites")
@commands.has_permissions(administrator=True)
async def addinvites_command(ctx, member: MemberOrID, amount: int):
    """Add invites to a user"""
    if amount <= 0:
        await ctx.send("Please specify a positive amount.")
        return
    
    new_total = await add_invites(ctx.guild.id, member.id, amount)
    
    embed = discord.Embed(
        title="➕ Invites Added",
        description=f"Added **{amount}** invite(s) to {member.display_name}",
        color=discord.Color.green()
    )
    embed.add_field(name="New Total", value=str(new_total))
    await ctx.send(embed=embed)


@bot.command(name="removeinvites")
@commands.has_permissions(administrator=True)
async def removeinvites_command(ctx, member: MemberOrID, amount: int):
    """Remove invites from a user"""
    if amount <= 0:
        await ctx.send("Please specify a positive amount.")
        return
    
    new_total = await add_invites(ctx.guild.id, member.id, -amount)
    
    embed = discord.Embed(
        title="➖ Invites Removed",
        description=f"Removed **{amount}** invite(s) from {member.display_name}",
        color=discord.Color.orange()
    )
    embed.add_field(name="New Total", value=str(new_total))
    await ctx.send(embed=embed)


@bot.command(name="clearinvites")
@commands.has_permissions(administrator=True)
async def clearinvites_command(ctx):
    """Clear all invite data for the server"""
    await clear_invite_data(ctx.guild.id)
    await ctx.send("Invite data cleared.")


@bot.command(name="resetmyinvites")
async def resetmyinvites_command(ctx):
    """Reset the invoking user's invite data"""
    await reset_user_invites(ctx.guild.id, ctx.author.id)
    await ctx.send("Your invite data has been reset.")


@bot.command(name="messages", aliases=["m"])
async def messages_command(ctx, member: MemberOrID = None):
    """Show total message count of a user"""
    target = member or ctx.author
    stats = await get_messages(ctx.guild.id, target.id)

    embed = discord.Embed(
        title=f"{target.display_name}'s Messages",
        description=(
            f"All time : {stats['messages']} messages in this server !\n"
            f"Today : {stats['daily_messages']} messages in this server\n\n"
            f"▶ Discover new events here!\n\n"
            f"Messages are being updated in real-time"
        ),
        color=discord.Color.from_str("#2b2d31")
    )
    await ctx.send(embed=embed)


@messages_command.error
async def messages_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "messages", "[@user]"))
        return
    raise error


@bot.command(name="addmessages")
@commands.has_permissions(administrator=True)
async def addmessages_command(ctx, member: MemberOrID, amount: int):
    """Add messages to a user"""
    if amount <= 0:
        await ctx.send(embed=build_messages_embed(
            ctx,
            "Missing required argument(s).",
            "Usage: `.addmessages <member> <amount>`"
        ))
        return

    await add_messages(ctx.guild.id, member.id, amount)

    embed = build_messages_embed(
        ctx,
        "Success",
        f"Successfully added {amount} messages to {member.display_name} !"
    )
    await ctx.send(embed=embed)


@bot.command(name="removemessages")
@commands.has_permissions(administrator=True)
async def removemessages_command(ctx, member: MemberOrID, amount: int):
    """Remove messages from a user"""
    if amount <= 0:
        await ctx.send(embed=build_messages_embed(
            ctx,
            "Missing required argument(s).",
            "Usage: `.removemessages <member> <amount>`"
        ))
        return

    await add_messages(ctx.guild.id, member.id, -amount)

    embed = build_messages_embed(
        ctx,
        "Success",
        f"Successfully removed {amount} messages from {member.display_name} !"
    )
    await ctx.send(embed=embed)


@bot.command(name="blacklistchannel")
@commands.has_permissions(administrator=True)
async def blacklistchannel_command(ctx, channel: discord.TextChannel):
    """Do not count messages from this channel"""
    await blacklist_message_channel(ctx.guild.id, channel.id)
    await ctx.send(embed=build_messages_embed(
        ctx,
        "Message blacklisted channels",
        f"Blacklisted #{channel.name}, I will not count messages posted in that channel"
    ))


@bot.command(name="unblacklistchannel")
@commands.has_permissions(administrator=True)
async def unblacklistchannel_command(ctx, channel: discord.TextChannel):
    """Remove a channel from the message blacklist"""
    await unblacklist_message_channel(ctx.guild.id, channel.id)
    await ctx.send(embed=build_messages_embed(
        ctx,
        "Message blacklisted channels",
        f"Unblacklisted #{channel.name}, I will count messages again"
    ))


@bot.command(name="blacklistedchannels")
async def blacklistedchannels_command(ctx):
    """Show all blacklisted channels"""
    channel_ids = await get_blacklisted_channels(ctx.guild.id)
    if not channel_ids:
        await ctx.send(embed=build_messages_embed(
            ctx,
            "Message blacklisted channels",
            "No blacklisted channels configured."
        ))
        return

    lines = []
    for channel_id in channel_ids:
        channel = ctx.guild.get_channel(channel_id)
        lines.append(f"#{channel.name}" if channel else f"Deleted Channel ({channel_id})")

    embed = build_messages_embed(
        ctx,
        "Message blacklisted channels",
        "\n".join(lines)
    )
    await ctx.send(embed=embed)


@bot.command(name="clearmessages")
@commands.has_permissions(administrator=True)
async def clearmessages_command(ctx):
    """Reset all message data in server"""
    await clear_all_messages(ctx.guild.id)
    await ctx.send(embed=build_messages_embed(
        ctx,
        "Success",
        "All message tracking data has been reset."
    ))


@bot.command(name="resetmymessages")
async def resetmymessages_command(ctx):
    """Reset own message count"""
    await reset_user_messages(ctx.guild.id, ctx.author.id)
    await ctx.send(embed=build_messages_embed(
        ctx,
        "Success",
        "Your message count has been reset."
    ))


@addmessages_command.error
async def addmessages_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "addmessages", "<member> <amount>"))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "addmessages", "<member> <amount>"))
        return
    raise error


@removemessages_command.error
async def removemessages_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "removemessages", "<member> <amount>"))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "removemessages", "<member> <amount>"))
        return
    raise error


@blacklistchannel_command.error
async def blacklistchannel_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "blacklistchannel", "<channel>"))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "blacklistchannel", "<channel>"))
        return
    raise error


@unblacklistchannel_command.error
async def unblacklistchannel_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "unblacklistchannel", "<channel>"))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(embed=build_messages_usage_embed(ctx, "unblacklistchannel", "<channel>"))
        return
    raise error


@bot.command(name="lb", aliases=["leaderboard"])
async def leaderboard_command(ctx, category: str = None):
    """Show leaderboard stats"""
    category_map = {
        "i": "invites",
        "inv": "invites",
        "invites": "invites",
        "m": "messages",
        "messages": "messages",
        "d": "dailymessages",
        "dailymessages": "dailymessages",
    }

    if not category:
        await ctx.send(embed=build_messages_embed(
            ctx,
            "Missing required argument(s).",
            "Usage: `.lb <m | d | i>`"
        ))
        return

    category = category_map.get(category.lower())
    if not category:
        await ctx.send(embed=build_messages_embed(
            ctx,
            "Missing required argument(s).",
            "Usage: `.lb <m | d | i>`"
        ))
        return

    if category in ["invites", "inv"]:
        leaderboard = await get_leaderboard(ctx.guild.id, limit=None)

        if not leaderboard:
            embed = discord.Embed(
                title="Invite Leaderboard",
                description="No invite data available yet.",
                color=discord.Color.from_str("#2b2d31")
            )
            embed.set_footer(text="Page 1/1")
            await ctx.send(embed=embed)
            return

        entries = []
        for rank, (user_id, count) in enumerate(leaderboard, start=1):
            try:
                user = await bot.fetch_user(user_id)
                entries.append(
                    f"#{rank} {getattr(user, 'display_name', user.name)} • "
                    f"{count} invite{'s' if count != 1 else ''}"
                )
            except:
                entries.append(f"#{rank} User({user_id}) • {count} invite{'s' if count != 1 else ''}")

        view = LeaderboardView(ctx.author.id, "Invite Leaderboard", entries)
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message
        return

    if category in ["messages", "dailymessages"]:
        stat_column = "messages" if category == "messages" else "daily_messages"
        leaderboard = await leaderboard_messages(ctx.guild.id, column=stat_column, limit=None)
        title = "Messages Leaderboard" if category == "messages" else "Daily Messages Leaderboard"

        if not leaderboard:
            embed = discord.Embed(
                title=title,
                description="No message data available yet.",
                color=discord.Color.from_str("#2b2d31")
            )
            embed.set_footer(text="Page 1/1")
            await ctx.send(embed=embed)
            return

        entries = []
        for rank, (user_id, count) in enumerate(leaderboard, start=1):
            try:
                user = await bot.fetch_user(user_id)
                entries.append(
                    f"#{rank} {getattr(user, 'display_name', user.name)} • "
                    f"{count} message{'s' if count != 1 else ''}"
                )
            except:
                entries.append(f"#{rank} User({user_id}) • {count} message{'s' if count != 1 else ''}")

        view = LeaderboardView(
            ctx.author.id,
            title,
            entries,
            intro_text="The messages are being updated in real-time!"
        )
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.message = message
        return

    await ctx.send(embed=build_messages_embed(
        ctx,
        "Missing required argument(s).",
        "Usage: `.lb <m | d | i>`"
    ))


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg = message.content.lower()
    current_prefix = get_command_prefix(bot, message)
    first_word = message.content.split(maxsplit=1)[0].lower() if message.content.strip() else ""
    is_admin_user = bool(
        message.guild
        and (
            message.author.guild_permissions.administrator
            or message.author.guild_permissions.manage_guild
        )
    )
    no_prefix_blocked_channel = (
        message.guild is not None
        and message.channel.id == NO_PREFIX_DISABLED_CHANNEL_ID
    )
    is_command_message = message.content.startswith(current_prefix) or (
        is_admin_user and first_word in NO_PREFIX_COMMANDS and not no_prefix_blocked_channel
    )

    if (
        message.guild
        and message.channel.id == MEDIA_ONLY_CHANNEL_ID
        and not message.author.bot
        and not message.attachments
        and not message.embeds
    ):
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await message.channel.send("This channel is for media only.", delete_after=5)
        return

    if (
        message.guild
        and message.guild.id == LINK_FILTER_GUILD_ID
        and not message.author.bot
        and message.content
        and message_has_blocked_link(message.content)
    ):
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        return

    if (
        message.guild
        and not message.author.bot
        and not message.content.startswith(current_prefix)
        and not no_prefix_blocked_channel
    ):
        if is_admin_user and first_word in NO_PREFIX_COMMANDS:
            prefixed_message = copy.copy(message)
            prefixed_message.content = f"{DEFAULT_PREFIX}{message.content}"
            ctx = await bot.get_context(prefixed_message)
            if ctx.valid:
                await bot.invoke(ctx)
                return
    
    # ===== SPAM DETECTION & PROTECTION =====
    if not message.author.bot and message.guild:
        if not await is_message_channel_blacklisted(message.guild.id, message.channel.id):
            await add_message(message.guild.id, message.author.id)

        # Check for spam
        spam_tracker[message.author.id].append(datetime.now(timezone.utc))
        
        if check_spam(message.author.id):
            # User is spamming
            try:
                # Timeout the user
                await message.author.timeout(
                    timedelta(seconds=SPAM_MUTE_DURATION),
                    reason="Spam detection"
                )
                log_moderation_action(
                    message.guild.id,
                    "spam_mute",
                    "System",
                    message.author,
                    "Automatic spam detection"
                )
                
                embed = discord.Embed(
                    title="🚫 Spam Detected",
                    description=f"{message.author.mention} has been muted for spam.",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed, delete_after=10)
                
                # Delete the spam messages
                await message.delete()
                return
            except:
                pass

    if not no_prefix_blocked_channel and bot.user in message.mentions and not message.reference:
        cleaned = message.content.replace(bot.user.mention, "").strip()
        nickname_mention = f"<@!{bot.user.id}>"
        cleaned = cleaned.replace(nickname_mention, "").strip()

        if not cleaned:
            ctx = await bot.get_context(message)
            await send_lunexa_welcome(ctx)
            return

    if msg == "role" or msg.startswith("role ") or msg == "!role" or msg.startswith("!role "):
        await handle_role_toggle(message)
        return

    if msg == "afk" or msg.startswith("afk "):
        if not message.guild:
            await message.channel.send("AFK nickname changes only work inside a server.")
            return

        afk_reason = message.content[3:].strip() or None
        reason_text = format_afk_reason(afk_reason)
        await message.channel.send(
            f"{message.author.mention} are you going AFK?{reason_text}",
            view=AFKConfirmView(message.author, afk_reason),
        )
        return

    if message.guild:
        afk_data = await get_afk_state(message.guild.id, message.author.id)
    else:
        afk_data = None

    if afk_data:
        afk_duration = format_duration(afk_data["since"])
        reason_text = format_afk_reason(afk_data.get("reason"))
        ping_summary = format_afk_pings(afk_data["pings"])
        await remove_afk(message.author)
        embed = discord.Embed(
            title="AFK",
            description=(
                f"{message.author.display_name} is no longer AFK\n\n"
                f"AFK for {afk_duration}.{reason_text}\n"
                f"{ping_summary}"
            ),
            color=discord.Color.from_str("#2b2d31")
        )
        await message.channel.send(embed=embed)

    for word in bad_words:
        if word in msg:
            reply = random.choice(responses)
            await message.channel.send(f"{message.author.mention} {reply}")
            break

    for mentioned_user in message.mentions:
        afk_data = await get_afk_state(message.guild.id, mentioned_user.id) if message.guild else None
        if afk_data:
            afk_duration = format_duration(afk_data["since"])
            reason_text = format_afk_reason(afk_data.get("reason"))
            afk_data["pings"].append(
                {
                    "by": message.author.display_name,
                    "url": message.jump_url,
                    "time": datetime.now(timezone.utc),
                }
            )
            await message.channel.send(
                f"{mentioned_user.mention} is AFK right now. AFK for {afk_duration}."
                f"{reason_text}"
            )
            continue

    if message.guild and not message.author.bot:
        if not is_command_message:
            for trigger, emoji in await get_auto_reactions(message.guild.id):
                if trigger in msg:
                    try:
                        await message.add_reaction(emoji)
                    except discord.HTTPException:
                        pass

            responder_allowed_at = autoresponder_cooldowns.get(message.author.id)
            if responder_allowed_at is None or datetime.now(timezone.utc) >= responder_allowed_at:
                for trigger, response in await get_autoresponders(message.guild.id):
                    if trigger in msg:
                        autoresponder_cooldowns[message.author.id] = (
                            datetime.now(timezone.utc) + timedelta(seconds=AUTORESPONDER_COOLDOWN_SECONDS)
                        )
                        await message.channel.send(response)
                        break
    await bot.process_commands(message)


# ===== HELP & SETUP COMMANDS =====

def get_main_help_embed():
    """Get the main help menu embed"""
    embed = discord.Embed(
        color=discord.Color.from_str("#2b2d31")
    )
    
    embed.set_author(
        name="whAlien ✨",
        icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None
    )
    
    embed.description = """Hey, I'm whAlien ✨
A powerful multipurpose bot with fast and reliable features

• **Prefix:** `.`
• **Total Commands:** 25+

• **Choose a category:**

🛡️ Moderation
⚙️ Utility
ℹ️ Info
📊 Messages
📨 Invites
⚡ Features"""
    
    embed.set_footer(text="Made with ❤️ by @_anuneet1x ")
    return embed


class ModuleView(discord.ui.View):
    """Module view with dropdown and back button"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.select(
        custom_id="help-menu-module",
        placeholder="Select Category From Here",
        options=[
            discord.SelectOption(label="Moderation", value="mod", emoji="🛡️"),
            discord.SelectOption(label="Utility", value="util", emoji="⚙️"),
            discord.SelectOption(label="Info", value="info", emoji="ℹ️"),
            discord.SelectOption(label="Messages", value="messages", emoji="📊"),
            discord.SelectOption(label="Invites", value="invites", emoji="📨"),
            discord.SelectOption(label="Features", value="features", emoji="⚡")
        ]
    )
    async def help_select_module(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle module selection"""
        selected = select.values[0]
        embed = self._get_module_embed(selected)
        await interaction.response.edit_message(embed=embed)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go back to main menu"""
        main_embed = get_main_help_embed()
        await interaction.response.edit_message(embed=main_embed, view=HelpView())
    
    def _get_module_embed(self, selected):
        """Get embed for the selected module"""
        if selected == "mod":
            return discord.Embed(
                title="🛡️ Moderation Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.warn @user [reason]` - Warn a member
`.mute @user [duration]` - Mute a member (e.g., 10m, 1h)
`.unmute @user` - Unmute a member
`.kick @user [reason]` - Kick a member
`.ban @user [reason]` - Ban a member
`.purge [amount]` - Delete messages
`.slowmode [seconds]` - Set channel slowmode
                """
            )
        
        elif selected == "util":
            return discord.Embed(
                title="⚙️ Utility Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.tickets` - Create support tickets
`.modlogs [@user]` - View moderation logs
`.afk [reason]` - Set AFK status
`role @user Role Name` - Toggle roles
`.serverinfo` - Show server details
`.userinfo [@user]` - Show user info
`.roleinfo @role` - Show role info
`.vcinfo [channel]` - Show voice channel info
`.avatar [@user]` - Show user's avatar
`.banner [@user]` - Show user's banner
`.guildbanner` - Show server banner
`.support` - Send support server link
`.membercount` - Show total members count
`.stats` - Show bot stats
`.shards` - Show shard info
`.permissions` - Show bot permissions
`.accountage [@user]` - Show account age
`.invite` - Show bot invite link
`.uptime` - Show bot uptime
`.botinfo` - Show bot information
`.ping` - Show bot latency
`.setprefix [new prefix]` - Change bot prefix
`.deleteprefix` - Reset prefix
`.gstart duration winners prize` - Start a giveaway
`.gend` - End the latest giveaway early
`.greroll` - Reroll the latest giveaway
                """
            )
        
        elif selected == "info":
            return discord.Embed(
                title="ℹ️ Info Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.about` / `.info` - Bot information
`.help` - Help menu (you are here)
`.setup` - Server setup guide
`.stats` - Server statistics
                """
            )

        elif selected == "messages":
            return discord.Embed(
                title="Messages",
                color=discord.Color.from_str("#2b2d31"),
                description="""
Keeps the count of users' messages

Core Commands
▶ `messages [@user]` - Displays message count of a user

Message Management
▶ `addmessages @user amount` - Add messages
▶ `removemessages @user amount` - Remove messages
▶ `clearmessages` - Clear all message data
▶ `resetmymessages` - Reset your messages

Channel Control
▶ `blacklistchannel #channel` - Exclude a channel
▶ `unblacklistchannel #channel` - Remove blacklist
▶ `blacklistedchannels` - Show blacklisted channels

Leaderboards
▶ `leaderboard messages` - Top message senders
▶ `leaderboard dailymessages` - Top daily senders
                """
            )
        
        elif selected == "invites":
            return discord.Embed(
                title="Invite logger / Invite tracker",
                color=discord.Color.from_str("#2b2d31"),
                description="""
Tracks and logs the server invites

Core Commands
▶ `invites [@user]` - Displays the invites stats of a member
▶ `inviter [@user]` - Displays the inviter of a server member
▶ `invited [@user]` - Displays the invited list of a member
▶ `inviteinfo` - Displays active invite codes

Invite Management
▶ `addinvites @user amount` - Add invites
▶ `removeinvites @user amount` - Remove invites
▶ `clearinvites` - Clear invite data
▶ `resetmyinvites` - Reset your invites

Leaderboard
▶ `leaderboard invites` - Show top inviters
                """
            )
        
        elif selected == "features":
            return discord.Embed(
                title="⚡ Features",
                color=discord.Color.from_str("#2b2d31"),
                description="""
✅ **Spam Protection** - Auto-mutes spammers
✅ **Raid Detection** - Detects mass joins
✅ **AFK System** - Manage AFK status
✅ **Auto-role** - Assigns roles on join
✅ **Bad Word Filter** - Filters profanity
✅ **Rotating Status** - Bot status changes every 7s
✅ **Ticket System** - Support ticket management
✅ **Moderation Logs** - Track all mod actions
✅ **Role Management** - Toggle roles easily
✅ **Invite Tracking** - Track who invited whom
                """
            )


class HelpView(discord.ui.View):
    """Interactive help menu with dropdown (main view)"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.select(
        custom_id="help-menu",
        placeholder="Select Category From Here",
        options=[
            discord.SelectOption(label="Moderation", value="mod", emoji="🛡️"),
            discord.SelectOption(label="Utility", value="util", emoji="⚙️"),
            discord.SelectOption(label="Info", value="info", emoji="ℹ️"),
            discord.SelectOption(label="Messages", value="messages", emoji="📊"),
            discord.SelectOption(label="Invites", value="invites", emoji="📨"),
            discord.SelectOption(label="Features", value="features", emoji="⚡")
        ]
    )
    async def help_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle help menu selection"""
        selected = select.values[0]
        embed = self._get_module_embed(selected)
        await interaction.response.edit_message(embed=embed, view=ModuleView())
    
    def _get_module_embed(self, selected):
        """Get embed for the selected module"""
        if selected == "mod":
            return discord.Embed(
                title="🛡️ Moderation Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.warn @user [reason]` - Warn a member
`.mute @user [duration]` - Mute a member (e.g., 10m, 1h)
`.unmute @user` - Unmute a member
`.kick @user [reason]` - Kick a member
`.ban @user [reason]` - Ban a member
`.purge [amount]` - Delete messages
`.slowmode [seconds]` - Set channel slowmode
                """
            )
        
        elif selected == "util":
            return discord.Embed(
                title="⚙️ Utility Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.tickets` - Create support tickets
`.modlogs [@user]` - View moderation logs
`.afk [reason]` - Set AFK status
`role @user Role Name` - Toggle roles
`.serverinfo` - Show server details
`.userinfo [@user]` - Show user info
`.roleinfo @role` - Show role info
`.vcinfo [channel]` - Show voice channel info
`.avatar [@user]` - Show user's avatar
`.banner [@user]` - Show user's banner
`.guildbanner` - Show server banner
`.support` - Send support server link
`.membercount` - Show total members count
`.stats` - Show bot stats
`.shards` - Show shard info
`.permissions` - Show bot permissions
`.accountage [@user]` - Show account age
`.invite` - Show bot invite link
`.uptime` - Show bot uptime
`.botinfo` - Show bot information
`.ping` - Show bot latency
`.setprefix [new prefix]` - Change bot prefix
`.deleteprefix` - Reset prefix
`.gstart duration winners prize` - Start a giveaway
`.gend` - End the latest giveaway early
`.greroll` - Reroll the latest giveaway
                """
            )
        
        elif selected == "info":
            return discord.Embed(
                title="ℹ️ Info Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.about` / `.info` - Bot information
`.help` - Help menu (you are here)
`.setup` - Server setup guide
`.stats` - Server statistics
                """
            )

        elif selected == "messages":
            return discord.Embed(
                title="Messages",
                color=discord.Color.from_str("#2b2d31"),
                description="""
Keeps the count of users' messages

Core Commands
▶ `messages [@user]` - Displays message count of a user

Message Management
▶ `addmessages @user amount` - Add messages
▶ `removemessages @user amount` - Remove messages
▶ `clearmessages` - Clear all message data
▶ `resetmymessages` - Reset your messages

Channel Control
▶ `blacklistchannel #channel` - Exclude a channel
▶ `unblacklistchannel #channel` - Remove blacklist
▶ `blacklistedchannels` - Show blacklisted channels

Leaderboards
▶ `leaderboard messages` - Top message senders
▶ `leaderboard dailymessages` - Top daily senders
                """
            )
        
        elif selected == "invites":
            return discord.Embed(
                title="Invite logger / Invite tracker",
                color=discord.Color.from_str("#2b2d31"),
                description="""
Tracks and logs the server invites

Core Commands
▶ `invites [@user]` - Displays the invites stats of a member
▶ `inviter [@user]` - Displays the inviter of a server member
▶ `invited [@user]` - Displays the invited list of a member
▶ `inviteinfo` - Displays active invite codes

Invite Management
▶ `addinvites @user amount` - Add invites
▶ `removeinvites @user amount` - Remove invites
▶ `clearinvites` - Clear invite data
▶ `resetmyinvites` - Reset your invites

Leaderboard
▶ `leaderboard invites` - Show top inviters
                """
            )
        
        elif selected == "features":
            return discord.Embed(
                title="⚡ Features",
                color=discord.Color.from_str("#2b2d31"),
                description="""
✅ **Spam Protection** - Auto-mutes spammers
✅ **Raid Detection** - Detects mass joins
✅ **AFK System** - Manage AFK status
✅ **Auto-role** - Assigns roles on join
✅ **Bad Word Filter** - Filters profanity
✅ **Rotating Status** - Bot status changes every 7s
✅ **Ticket System** - Support ticket management
✅ **Moderation Logs** - Track all mod actions
✅ **Role Management** - Toggle roles easily
✅ **Invite Tracking** - Track who invited whom
                """
            )


def get_main_help_embed():
    """Get the main help menu embed."""
    embed = discord.Embed(color=discord.Color.from_str("#2b2d31"))
    embed.set_author(
        name="whAlien ✨",
        icon_url=bot.user.display_avatar.url if bot.user.display_avatar else None,
    )
    embed.description = """Hey, I'm whAlien ✨
A powerful multipurpose bot with fast and reliable features

• **Prefix:** `.`
• **Total Commands:** 35+

• **Choose a category:**

🛡️ Moderation
⚙️ Utility
ℹ️ Info
📊 Messages
📨 Invites
🎁 Giveaway
🤖 Automation
🎭 Roles
📁 Media"""
    embed.set_footer(text="Made with ❤️ by @_anuneet1x ")
    return embed


def get_help_module_embed(selected):
    if selected == "mod":
        return discord.Embed(
            title="🛡️ Moderation Commands",
            color=discord.Color.from_str("#2b2d31"),
            description="""
`.warn @user [reason]` - Warn a member
`.mute @user [duration]` - Mute a member (e.g., 10m, 1h)
`.unmute @user` - Unmute a member
`.kick @user [reason]` - Kick a member
`.ban @user [reason]` - Ban a member
`.purge [amount]` - Delete messages
`.slowmode [seconds]` - Set channel slowmode
            """
        )

    if selected == "util":
        return discord.Embed(
            title="⚙️ Utility Commands",
            color=discord.Color.from_str("#2b2d31"),
            description="""
`.tickets` - Create support tickets
`.modlogs [@user]` - View moderation logs
`.afk [reason]` - Set AFK status
`role @user Role Name` - Toggle roles
`.serverinfo` - Show server details
`.userinfo [@user]` - Show user info
`.roleinfo @role` - Show role info
`.vcinfo [channel]` - Show voice channel info
`.avatar [@user]` - Show user's avatar
`.banner [@user]` - Show user's banner
`.guildbanner` - Show server banner
`.support` - Send support server link
`.membercount` - Show total members count
`.stats` - Show bot stats
`.shards` - Show shard info
`.permissions` - Show bot permissions
`.accountage [@user]` - Show account age
`.invite` - Show bot invite link
`.uptime` - Show bot uptime
`.botinfo` - Show bot information
`.ping` - Show bot latency
`.setprefix [new prefix]` - Change bot prefix
`.deleteprefix` - Reset prefix
            """
        )

    if selected == "info":
        return discord.Embed(
            title="ℹ️ Info Commands",
            color=discord.Color.from_str("#2b2d31"),
            description="""
`.about` / `.info` - Bot information
`.help` - Help menu (you are here)
`.setup` - Server setup guide
`.stats` - Server statistics
            """
        )

    if selected == "messages":
        return discord.Embed(
            title="Messages",
            color=discord.Color.from_str("#2b2d31"),
            description="""
Keeps the count of users' messages

Core Commands
▶ `messages [@user]` - Displays message count of a user

Message Management
▶ `addmessages @user amount` - Add messages
▶ `removemessages @user amount` - Remove messages
▶ `clearmessages` - Clear all message data
▶ `resetmymessages` - Reset your messages

Channel Control
▶ `blacklistchannel #channel` - Exclude a channel
▶ `unblacklistchannel #channel` - Remove blacklist
▶ `blacklistedchannels` - Show blacklisted channels

Leaderboards
▶ `leaderboard messages` - Top message senders
▶ `leaderboard dailymessages` - Top daily senders
            """
        )

    if selected == "invites":
        return discord.Embed(
            title="Invite logger / Invite tracker",
            color=discord.Color.from_str("#2b2d31"),
            description="""
Tracks and logs the server invites

Core Commands
▶ `invites [@user]` - Displays the invites stats of a member
▶ `inviter [@user]` - Displays the inviter of a server member
▶ `invited [@user]` - Displays the invited list of a member
▶ `inviteinfo` - Displays active invite codes

Invite Management
▶ `addinvites @user amount` - Add invites
▶ `removeinvites @user amount` - Remove invites
▶ `clearinvites` - Clear invite data
▶ `resetmyinvites` - Reset your invites

Leaderboard
▶ `leaderboard invites` - Show top inviters
            """
        )

    if selected == "giveaway":
        return get_giveaway_help_embed()

    if selected == "automation":
        return discord.Embed(
            title="Automation",
            color=discord.Color.from_str("#2b2d31"),
            description="""
▶ `autoresponder add <trigger> <response>` - Add autoresponder
▶ `autoresponder remove <trigger>` - Remove autoresponder
▶ `autoresponder show` - Show autoresponders

▶ `autoreact add <trigger> <emoji>` - Add auto reaction
▶ `autoreact remove <trigger>` - Remove auto reaction
▶ `autoreact show` - Show auto reactions

▶ `sticky set <message>` - Save sticky message
▶ `sticky remove` - Remove sticky message
▶ `sticky show` - Show sticky message
            """
        )

    if selected == "roles":
        return discord.Embed(
            title="Roles",
            color=discord.Color.from_str("#2b2d31"),
            description="""
▶ `setup role <role>` - Save base role
▶ `setup role remove <role>` - Remove base role
▶ `setup role show` - Show saved role
            """
        )

    if selected == "media":
        return discord.Embed(
            title="Media",
            color=discord.Color.from_str("#2b2d31"),
            description=f"""
Media-only channel
▶ Only attachments and embeds are allowed
▶ Channel ID: `{MEDIA_ONLY_CHANNEL_ID}`
            """
        )

    return get_main_help_embed()


class ModuleView(discord.ui.View):
    """Module view with dropdown and back button."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="help-menu-module-clean",
        placeholder="Select Category From Here",
        options=[
            discord.SelectOption(label="Moderation", value="mod", emoji="🛡️"),
            discord.SelectOption(label="Utility", value="util", emoji="⚙️"),
            discord.SelectOption(label="Info", value="info", emoji="ℹ️"),
            discord.SelectOption(label="Messages", value="messages", emoji="📊"),
            discord.SelectOption(label="Invites", value="invites", emoji="📨"),
            discord.SelectOption(label="Giveaway", value="giveaway", emoji="🎁"),
            discord.SelectOption(label="Automation", value="automation", emoji="🤖"),
            discord.SelectOption(label="Roles", value="roles", emoji="🎭"),
            discord.SelectOption(label="Media", value="media", emoji="📁"),
        ],
    )
    async def help_select_module(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.edit_message(embed=get_help_module_embed(select.values[0]), view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=get_main_help_embed(), view=HelpView())


class HelpView(discord.ui.View):
    """Interactive help menu with dropdown."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        custom_id="help-menu-clean",
        placeholder="Select Category From Here",
        options=[
            discord.SelectOption(label="Moderation", value="mod", emoji="🛡️"),
            discord.SelectOption(label="Utility", value="util", emoji="⚙️"),
            discord.SelectOption(label="Info", value="info", emoji="ℹ️"),
            discord.SelectOption(label="Messages", value="messages", emoji="📊"),
            discord.SelectOption(label="Invites", value="invites", emoji="📨"),
            discord.SelectOption(label="Giveaway", value="giveaway", emoji="🎁"),
            discord.SelectOption(label="Automation", value="automation", emoji="🤖"),
            discord.SelectOption(label="Roles", value="roles", emoji="🎭"),
            discord.SelectOption(label="Media", value="media", emoji="📁"),
        ],
    )
    async def help_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.edit_message(
            embed=get_help_module_embed(select.values[0]),
            view=ModuleView(),
        )


@bot.command(name="help", aliases=["commands", "cmd"])
async def commands_command(ctx):
    """Show bot help and all available commands"""
    embed = get_main_help_embed()
    await ctx.send(embed=embed, view=HelpView())


@bot.group(name="setup", invoke_without_command=True)
@commands.has_permissions(administrator=True)
async def setup_command(ctx):
    """Setup bot configuration for your server"""
    embed = discord.Embed(
        title="⚙️ SBot Setup Guide",
        color=discord.Color.green(),
        description="Here's how to set up SBot for your server:"
    )

    embed.add_field(
        name="1️⃣ Create Required Roles",
        value="Create a 'Muted' role for muting system",
        inline=False
    )

    embed.add_field(
        name="2️⃣ Create Categories",
        value="""
Create 'Tickets' category for support tickets
Create 'Temporary Channels' for temp VCs
        """,
        inline=False
    )

    embed.add_field(
        name="3️⃣ Configure Role Base",
        value="Use `.setup role <role>` to save the base role configuration",
        inline=False
    )

    embed.add_field(
        name="4️⃣ Create Ticket Panel",
        value="Use `.sendtickets` to create the ticket panel",
        inline=False
    )

    embed.add_field(
        name="4ï¸âƒ£ Configure Permission Role Automation",
        value=(
            "Use `.setup permrole add <source role> <target role>` to auto-assign hidden permission roles.\n"
            "Example: `.setup permrole add @Virelya @OS`"
        ),
        inline=False
    )

    embed.set_footer(text="All set! Enjoy SBot")
    await ctx.send(embed=embed)


@setup_command.group(name="role", invoke_without_command=True)
@commands.has_permissions(administrator=True)
async def setup_role_command(ctx, role: discord.Role = None):
    if role is None:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Setup Role",
            "Usage: `.setup role <role>`",
            success=False,
        ))
        return

    await set_custom_role(ctx.guild.id, role.id)
    await sync_base_roles_for_guild(ctx.guild)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Setup Role",
        f"Saved role configuration for {role.mention}.",
    ))


@setup_role_command.command(name="remove")
@commands.has_permissions(administrator=True)
async def setup_role_remove_command(ctx, role: discord.Role):
    current_role_id = await get_custom_role_id(ctx.guild.id)
    if current_role_id != role.id:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Setup Role",
            "That role is not the saved role configuration.",
            success=False,
        ))
        return

    await remove_custom_role(ctx.guild.id, role.id)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Setup Role",
        f"Removed role configuration for {role.mention}.",
    ))


@setup_role_command.command(name="show")
@commands.has_permissions(administrator=True)
async def setup_role_show_command(ctx):
    role_id = await get_custom_role_id(ctx.guild.id)
    if not role_id:
        await ctx.send(embed=build_automation_embed(ctx, "Setup Role", "No role configuration saved yet."))
        return

    role = ctx.guild.get_role(role_id)
    role_text = role.mention if role else f"Deleted Role ({role_id})"
    await ctx.send(embed=build_automation_embed(ctx, "Setup Role", f"Saved role: {role_text}"))


@setup_role_command.error
@setup_role_remove_command.error
async def setup_role_error(ctx, error):
    await automation_command_error(ctx, error)


@setup_command.group(name="permrole", invoke_without_command=True)
@commands.has_permissions(administrator=True)
async def setup_permrole_command(ctx):
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Permission Role Automation",
        (
            "Use `.setup permrole add <source role> <target role>` to create a link.\n"
            "Use `.setup permrole remove <source role> <target role>` to delete a link.\n"
            "Use `.setup permrole list` to view all links.\n"
            "Use `.setup permrole sync` to force a resync now."
        ),
    ))


@setup_permrole_command.command(name="add")
@commands.has_permissions(administrator=True)
async def setup_permrole_add_command(ctx, source_role: discord.Role, target_role: discord.Role):
    if source_role.id == target_role.id:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Permission Role Automation",
            "Source role and target role cannot be the same.",
            success=False,
        ))
        return

    await add_permission_role_link(ctx.guild.id, source_role.id, target_role.id)
    await sync_permission_roles_for_guild(ctx.guild)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Permission Role Automation",
        f"Linked {source_role.mention} -> {target_role.mention}. Members with the source role will now get the target role automatically.",
    ))


@setup_permrole_command.command(name="remove")
@commands.has_permissions(administrator=True)
async def setup_permrole_remove_command(ctx, source_role: discord.Role, target_role: discord.Role):
    await remove_permission_role_link(ctx.guild.id, source_role.id, target_role.id)
    await sync_permission_roles_for_guild(ctx.guild)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Permission Role Automation",
        f"Removed link {source_role.mention} -> {target_role.mention}.",
    ))


@setup_permrole_command.command(name="list")
@commands.has_permissions(administrator=True)
async def setup_permrole_list_command(ctx):
    links = await get_permission_role_links(ctx.guild.id)
    if not links:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Permission Role Automation",
            "No permission role links are configured yet.",
        ))
        return

    lines = []
    for row in links:
        source_role = ctx.guild.get_role(row["source_role_id"])
        target_role = ctx.guild.get_role(row["target_role_id"])
        source_text = source_role.mention if source_role else f"Deleted Role ({row['source_role_id']})"
        target_text = target_role.mention if target_role else f"Deleted Role ({row['target_role_id']})"
        lines.append(f"{source_text} -> {target_text}")

    await ctx.send(embed=build_automation_embed(
        ctx,
        "Permission Role Automation",
        "\n".join(lines),
    ))


@setup_permrole_command.command(name="sync")
@commands.has_permissions(administrator=True)
async def setup_permrole_sync_command(ctx):
    await sync_permission_roles_for_guild(ctx.guild)
    await ctx.send(embed=build_automation_embed(
        ctx,
        "Permission Role Automation",
        "Permission role links synced for this server.",
    ))


@setup_permrole_command.error
@setup_permrole_add_command.error
@setup_permrole_remove_command.error
@setup_permrole_list_command.error
@setup_permrole_sync_command.error
async def setup_permrole_error(ctx, error):
    await automation_command_error(ctx, error)


@bot.command(name="stats")
async def stats_command(ctx):
    """Show bot statistics"""
    total_users = sum(guild.member_count or 0 for guild in bot.guilds)
    command_count = len(bot.commands)
    embed = discord.Embed(
        title="📊 Bot Statistics",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Overview",
        value=(
            f"Servers: **{len(bot.guilds)}**\n"
            f"Users: **{total_users}**\n"
            f"Commands: **{command_count}**"
        ),
        inline=True
    )

    embed.add_field(
        name="Runtime",
        value=(
            f"Latency: **{round(bot.latency * 1000)}ms**\n"
            f"Uptime: **{format_relative_duration(BOT_START_TIME)}**\n"
            f"Shard Count: **{bot.shard_count or 1}**"
        ),
        inline=True
    )

    await ctx.send(embed=embed)


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set. Add it to .env before starting the bot.")

bot.run(token)

