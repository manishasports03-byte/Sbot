import os
import random
import re
import copy
import io
import json
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
storage_lock = asyncio.Lock()
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "bot_storage.json")
DEFAULT_STORAGE = {
    "invite_stats": {},
    "inviter_map": {},
    "invite_events": [],
    "message_stats": {},
    "message_blacklist": {},
    "bot_state": {},
    "guild_settings": {},
    "afk_users": {},
    "autoresponders": {},
    "auto_reactions": {},
    "sticky_messages": {},
    "birthday_users": {},
}
storage_data = {}
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
    "remind",
    "gstart", "gend", "greroll",
    "steal", "roleicon",
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
TICKET_HELPER_ROLE_ID = 1500035607966257282
TICKET_PANEL_MESSAGE_KEY = "ticket_panel_message_id"
TICKET_PANEL_TITLE = "Create Ticket"
TICKET_BUTTON_COOLDOWN_SECONDS = 15
ticket_button_cooldowns = {}
VERIFICATION_PANEL_MESSAGE_KEY = "verification_panel_message_id"
VERIFICATION_PANEL_TITLE = "Security"
VERIFICATION_PANEL_IMAGE_URL = "https://media.discordapp.net/attachments/1379072095899615232/1494284320599179356/ezgif-549dd942b0d67c6a.gif?ex=69f875b8&is=69f72438&hm=d9b2a3ac492c848e128e7ff5c715cfd33a5dc2505f64c470e957f27c5e92bfeb&=&width=335&height=289"
UNVERIFIED_ROLE_ID = 1500562676781416710
VERIFIED_ROLE_ID = 1500562574511444139
PEASANT_ROLE_ID = 1500565277845487836
MEDIA_ONLY_CHANNEL_ID = 1379065330957160560
ONBOARDING_CATEGORY_ID = 1379780404894236744
CHANT_TO_START_CHANNEL_ID = 1379780588193448027
SECURITY_VERIFICATION_CHANNEL_ID = 1442881449434026045
JOIN_LEAVE_LOG_CHANNEL_ID = 1501152051659542599
BLOCKED_WIZARDS_CATEGORY_IDS = {
    1391451602178801766,
    1379076786226462772,
}
WIZARDS_SEND_CATEGORY_IDS = {
    1379095007503323156,
    1379083372998955099,
}
BLOCKED_WIZARDS_CHANNEL_IDS = {
    1493973652100874371,
}
WIZARDS_ALLOWED_VOICE_CHANNEL_IDS = {
    1494320978564612277,
}
WIZARDS_ALLOWED_VOICE_CATEGORY_IDS = {
    1379083372998955099,
}
WIZARDS_VIEW_ONLY_VOICE_CHANNEL_IDS = {
    1379100622309036204,
}
WIZARDS_MUTED_VOICE_CATEGORY_IDS = {
    1379083372998955099,
}
WIZARDS_VOICE_CATEGORY_ID = 1379052516863381637
RESTRICTED_WIZARDS_VOICE_CHANNEL_ID = 1379826132509262025
SPECIAL_WIZARDS_VOICE_ACCESS_ROLE_ID = 1379461606127177728
BIRTHDAY_ROLE_ID = 1380464856016097341
VIRELYA_ROLE_ID = 1500563026112286781
SEARASTA_ROLE_ID = 1500563240965505034
ARCHWIZARD_ROLE_ID = 1500563396473524365
HIGH_ARCANIST_ROLE_ID = 1500563428941500427
NEBULARC_ROLE_ID = 1500563495098515656
SPELLWARDEN_ROLE_ID = 1500563546377949316
ENIGMANCER_ROLE_ID = 1500563589906567268
ECHOKEEPER_ROLE_ID = 1500563626770173952
MELODIST_ROLE_ID = 1500563789525811342
APPOLO_ROLE_ID = 1500563961609719889
ECLIPSEBOUND_ELITE_ROLE_ID = 1500564044443029534
LUMINARY_ROLE_ID = 1500564161980141700
NOVA_WATCH_ROLE_ID = 1500564220607988024
CRYSTAL_MARSHAL_ROLE_ID = 1500564329215430748
EMBER_JUDGE_ROLE_ID = 1500564374039822597
CURSEMENDER_ROLE_ID = 1500564561030549654
WHISPER_BINDER_ROLE_ID = 1500564667561414657
DREAMWALKER_ROLE_ID = 1500564720661561374
ECLIPSED_SOULS_ROLE_ID = 1500564784947663063
MISERY_IMP_ROLE_ID = 1500564917197996212
ARCANE_SQUIRE_ROLE_ID = 1500565020822736936
WIZARDS_ROLE_ID = 1500565118138974209
OS_ROLE_ID = 1500560210224484505
MEDIA_ROLE_ID = 1500560404445659156
REQ_ROLE_ID = 1500560712982986803
KICK_ROLE_ID = 1500560891996012574
BAN_ROLE_ID = 1500561000812904478
MUTE_ROLE_ID = 1500561060388671640
VOICE_ROLE_ID = 1500561183122395367
PASS_ROLE_ID = 1500561399859122328
TICKET_ACCESS_ROLE_ID = 1500561695540641933
DEFAULT_PERMISSION_ROLE_LINKS = (
    (VIRELYA_ROLE_ID, OS_ROLE_ID),
    (VIRELYA_ROLE_ID, MEDIA_ROLE_ID),
    (SEARASTA_ROLE_ID, OS_ROLE_ID),
    (SEARASTA_ROLE_ID, MEDIA_ROLE_ID),
    (ARCHWIZARD_ROLE_ID, OS_ROLE_ID),
    (ARCHWIZARD_ROLE_ID, MEDIA_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, REQ_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, KICK_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, BAN_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, MUTE_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, VOICE_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, PASS_ROLE_ID),
    (HIGH_ARCANIST_ROLE_ID, MEDIA_ROLE_ID),
    (NEBULARC_ROLE_ID, REQ_ROLE_ID),
    (NEBULARC_ROLE_ID, KICK_ROLE_ID),
    (NEBULARC_ROLE_ID, MUTE_ROLE_ID),
    (NEBULARC_ROLE_ID, VOICE_ROLE_ID),
    (NEBULARC_ROLE_ID, PASS_ROLE_ID),
    (NEBULARC_ROLE_ID, MEDIA_ROLE_ID),
    (SPELLWARDEN_ROLE_ID, REQ_ROLE_ID),
    (SPELLWARDEN_ROLE_ID, KICK_ROLE_ID),
    (SPELLWARDEN_ROLE_ID, MUTE_ROLE_ID),
    (SPELLWARDEN_ROLE_ID, MEDIA_ROLE_ID),
    (ENIGMANCER_ROLE_ID, PASS_ROLE_ID),
    (ENIGMANCER_ROLE_ID, MEDIA_ROLE_ID),
    (ECHOKEEPER_ROLE_ID, VOICE_ROLE_ID),
    (ECHOKEEPER_ROLE_ID, MEDIA_ROLE_ID),
    (MELODIST_ROLE_ID, VOICE_ROLE_ID),
    (MELODIST_ROLE_ID, MEDIA_ROLE_ID),
    (APPOLO_ROLE_ID, MEDIA_ROLE_ID),
    (ECLIPSEBOUND_ELITE_ROLE_ID, MEDIA_ROLE_ID),
    (LUMINARY_ROLE_ID, MEDIA_ROLE_ID),
    (NOVA_WATCH_ROLE_ID, TICKET_ACCESS_ROLE_ID),
    (NOVA_WATCH_ROLE_ID, MEDIA_ROLE_ID),
    (CRYSTAL_MARSHAL_ROLE_ID, MEDIA_ROLE_ID),
    (EMBER_JUDGE_ROLE_ID, BAN_ROLE_ID),
    (EMBER_JUDGE_ROLE_ID, KICK_ROLE_ID),
    (EMBER_JUDGE_ROLE_ID, MUTE_ROLE_ID),
    (EMBER_JUDGE_ROLE_ID, MEDIA_ROLE_ID),
    (CURSEMENDER_ROLE_ID, BAN_ROLE_ID),
    (CURSEMENDER_ROLE_ID, MUTE_ROLE_ID),
    (CURSEMENDER_ROLE_ID, MEDIA_ROLE_ID),
    (WHISPER_BINDER_ROLE_ID, MEDIA_ROLE_ID),
    (DREAMWALKER_ROLE_ID, MEDIA_ROLE_ID),
    (ECLIPSED_SOULS_ROLE_ID, MEDIA_ROLE_ID),
    (MISERY_IMP_ROLE_ID, MEDIA_ROLE_ID),
    (ARCANE_SQUIRE_ROLE_ID, MEDIA_ROLE_ID),
    (WIZARDS_ROLE_ID, MEDIA_ROLE_ID),
)
PERMISSION_BUNDLE_SOURCE_ROLE_IDS = {source_role_id for source_role_id, _ in DEFAULT_PERMISSION_ROLE_LINKS}
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
    """Load guild prefixes from local storage into cache."""
    guild_prefix_cache.clear()
    for guild_id, prefix in storage_data.get("guild_settings", {}).items():
        try:
            guild_prefix_cache[int(guild_id)] = prefix or DEFAULT_PREFIX
        except (TypeError, ValueError):
            continue


def ensure_storage_defaults(data):
    normalized = copy.deepcopy(DEFAULT_STORAGE)
    if isinstance(data, dict):
        for key, default_value in DEFAULT_STORAGE.items():
            value = data.get(key, copy.deepcopy(default_value))
            if isinstance(default_value, dict):
                normalized[key] = value if isinstance(value, dict) else {}
            elif isinstance(default_value, list):
                normalized[key] = value if isinstance(value, list) else []
            else:
                normalized[key] = value
    return normalized


async def save_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    async with storage_lock:
        temp_path = f"{DATA_FILE}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(storage_data, handle, indent=2, ensure_ascii=True)
        os.replace(temp_path, DATA_FILE)


async def create_tables():
    """Ensure the local storage file exists."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        await save_storage()
    print("Local storage ensured")


async def connect_db():
    global db, storage_data
    if db is not None:
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as handle:
                loaded_data = json.load(handle)
        except Exception as e:
            print("STORAGE ERROR:", e)
            loaded_data = {}
    else:
        loaded_data = {}

    storage_data = ensure_storage_defaults(loaded_data)
    db = storage_data
    await create_tables()
    await load_guild_prefixes()
    await load_afk_users()
    print(f"Local storage initialized successfully: {DATA_FILE}")

async def get_invites(guild_id, user_id):
    """Get invite count for a user."""
    return int(
        storage_data.get("invite_stats", {})
        .get(str(guild_id), {})
        .get(str(user_id), 0)
    )


async def add_invites(guild_id, user_id, amount):
    """Add invites to a user."""
    current = await get_invites(guild_id, user_id)
    new_total = max(0, current + amount)
    guild_stats = storage_data.setdefault("invite_stats", {}).setdefault(str(guild_id), {})
    guild_stats[str(user_id)] = new_total
    await save_storage()
    print(f"Saved invites for user: {user_id}")
    return new_total


async def set_inviter(guild_id, user_id, inviter_id):
    """Set who invited a user."""
    guild_inviter_map = storage_data.setdefault("inviter_map", {}).setdefault(str(guild_id), {})
    guild_inviter_map[str(user_id)] = inviter_id
    await save_storage()
    print(f"Saved inviter mapping for user: {user_id}")


async def get_inviter(guild_id, user_id):
    """Get who invited a user."""
    inviter_id = (
        storage_data.get("inviter_map", {})
        .get(str(guild_id), {})
        .get(str(user_id))
    )
    return int(inviter_id) if inviter_id is not None else None


async def get_invited_users(guild_id, inviter_id):
    """Get list of users invited by someone."""
    invited_users = []
    for user_id, saved_inviter_id in storage_data.get("inviter_map", {}).get(str(guild_id), {}).items():
        if int(saved_inviter_id) == inviter_id:
            invited_users.append(int(user_id))
    return sorted(invited_users)


async def log_invite_event(guild_id, user_id, inviter_id, event_type):
    storage_data.setdefault("invite_events", []).append(
        {
            "guild_id": guild_id,
            "user_id": user_id,
            "inviter_id": inviter_id,
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    await save_storage()
    print(f"Logged invite event {event_type} for user: {user_id}")


async def get_invite_event_count(guild_id, inviter_id, event_type, since=None):
    count = 0
    for event in storage_data.get("invite_events", []):
        if event.get("guild_id") != guild_id:
            continue
        if event.get("inviter_id") != inviter_id:
            continue
        if event.get("event_type") != event_type:
            continue
        if since is not None:
            created_at_text = event.get("created_at")
            if not created_at_text:
                continue
            try:
                created_at = datetime.fromisoformat(created_at_text)
            except ValueError:
                continue
            if created_at < since:
                continue
        count += 1
    return count


async def get_user_invite_event_count(guild_id, user_id, event_type):
    return sum(
        1
        for event in storage_data.get("invite_events", [])
        if event.get("guild_id") == guild_id
        and event.get("user_id") == user_id
        and event.get("event_type") == event_type
    )


async def get_leaderboard(guild_id, limit=10):
    """Get top inviters for a guild."""
    rows = sorted(
        (
            (int(user_id), int(invites))
            for user_id, invites in storage_data.get("invite_stats", {}).get(str(guild_id), {}).items()
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return rows if limit is None else rows[:limit]


async def clear_invite_data(guild_id):
    """Clear all invite data for a guild."""
    storage_data.setdefault("invite_stats", {}).pop(str(guild_id), None)
    storage_data.setdefault("inviter_map", {}).pop(str(guild_id), None)
    storage_data["invite_events"] = [
        event for event in storage_data.get("invite_events", []) if event.get("guild_id") != guild_id
    ]
    await save_storage()
    print(f"Cleared invite stats for guild: {guild_id}")
    print(f"Cleared inviter map for guild: {guild_id}")


async def reset_user_invites(guild_id, user_id):
    """Reset invite count for one user."""
    storage_data.setdefault("invite_stats", {}).setdefault(str(guild_id), {}).pop(str(user_id), None)
    await save_storage()
    print(f"Reset invites for user: {user_id}")


async def get_state_value(key):
    return storage_data.get("bot_state", {}).get(key)


async def set_state_value(key, value):
    storage_data.setdefault("bot_state", {})[key] = value
    await save_storage()
    print(f"Saved bot state key: {key}")


async def add_autoresponder(guild_id, trigger, response):
    normalized_trigger = trigger.lower()
    storage_data.setdefault("autoresponders", {}).setdefault(str(guild_id), {})[normalized_trigger] = response
    await save_storage()
    print(f"Saved autoresponder '{normalized_trigger}' for guild: {guild_id}")


async def remove_autoresponder(guild_id, trigger):
    normalized_trigger = trigger.lower()
    storage_data.setdefault("autoresponders", {}).setdefault(str(guild_id), {}).pop(normalized_trigger, None)
    await save_storage()
    print(f"Removed autoresponder '{normalized_trigger}' for guild: {guild_id}")


async def get_autoresponders(guild_id):
    responders = storage_data.get("autoresponders", {}).get(str(guild_id), {})
    return sorted(responders.items(), key=lambda item: item[0])


async def add_auto_reaction(guild_id, trigger, emoji):
    normalized_trigger = trigger.lower()
    storage_data.setdefault("auto_reactions", {}).setdefault(str(guild_id), {})[normalized_trigger] = emoji
    await save_storage()
    print(f"Saved autoreact '{normalized_trigger}' for guild: {guild_id}")


async def remove_auto_reaction(guild_id, trigger):
    normalized_trigger = trigger.lower()
    storage_data.setdefault("auto_reactions", {}).setdefault(str(guild_id), {}).pop(normalized_trigger, None)
    await save_storage()
    print(f"Removed autoreact '{normalized_trigger}' for guild: {guild_id}")


async def get_auto_reactions(guild_id):
    reactions = storage_data.get("auto_reactions", {}).get(str(guild_id), {})
    return sorted(reactions.items(), key=lambda item: item[0])


async def set_sticky_message(guild_id, message):
    storage_data.setdefault("sticky_messages", {})[str(guild_id)] = message
    await save_storage()
    print(f"Saved sticky message for guild: {guild_id}")


async def remove_sticky_message(guild_id):
    storage_data.setdefault("sticky_messages", {}).pop(str(guild_id), None)
    await save_storage()
    print(f"Removed sticky message for guild: {guild_id}")


async def get_sticky_message(guild_id):
    return storage_data.get("sticky_messages", {}).get(str(guild_id))


async def reset_daily_message_counts_if_needed():
    today = datetime.now(timezone.utc).date().isoformat()
    last_reset = await get_state_value(MESSAGE_DAILY_RESET_KEY)
    if last_reset == today:
        return

    for guild_stats in storage_data.get("message_stats", {}).values():
        for user_stats in guild_stats.values():
            user_stats["daily_messages"] = 0
    await save_storage()
    print("Reset daily message counts")
    await set_state_value(MESSAGE_DAILY_RESET_KEY, today)


async def set_birthday(guild_id, user_id, birth_month, birth_day):
    guild_birthdays = storage_data.setdefault("birthday_users", {}).setdefault(str(guild_id), {})
    guild_birthdays[str(user_id)] = {"birth_month": birth_month, "birth_day": birth_day}
    await save_storage()
    print(f"Saved birthday for user {user_id} in guild {guild_id}")


async def remove_birthday(guild_id, user_id):
    storage_data.setdefault("birthday_users", {}).setdefault(str(guild_id), {}).pop(str(user_id), None)
    await save_storage()
    print(f"Removed birthday for user {user_id} in guild {guild_id}")


async def get_birthday(guild_id, user_id):
    return (
        storage_data.get("birthday_users", {})
        .get(str(guild_id), {})
        .get(str(user_id))
    )


async def get_birthdays_for_day(birth_month, birth_day):
    matches = []
    for guild_id, guild_birthdays in storage_data.get("birthday_users", {}).items():
        for user_id, birthday in guild_birthdays.items():
            if birthday.get("birth_month") == birth_month and birthday.get("birth_day") == birth_day:
                matches.append({"guild_id": int(guild_id), "user_id": int(user_id)})
    return matches


def get_ist_today():
    return datetime.now(IST).date()


async def get_message_stats(guild_id, user_id):
    await reset_daily_message_counts_if_needed()
    row = (
        storage_data.get("message_stats", {})
        .get(str(guild_id), {})
        .get(str(user_id))
    )
    if row:
        return {
            "messages": int(row.get("messages", 0)),
            "daily_messages": int(row.get("daily_messages", 0)),
        }
    return {"messages": 0, "daily_messages": 0}


async def set_message_stats(guild_id, user_id, messages, daily_messages):
    guild_stats = storage_data.setdefault("message_stats", {}).setdefault(str(guild_id), {})
    guild_stats[str(user_id)] = {
        "messages": max(0, messages),
        "daily_messages": max(0, daily_messages),
    }
    await save_storage()
    print(f"Saved message stats for user: {user_id}")


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
    storage_data.setdefault("message_stats", {}).pop(str(guild_id), None)
    await save_storage()
    print(f"Cleared message stats for guild: {guild_id}")


async def reset_user_messages(guild_id, user_id):
    await set_message_stats(guild_id, user_id, 0, 0)


async def get_message_leaderboard(guild_id, column="messages", limit=10):
    if column not in {"messages", "daily_messages"}:
        return []

    await reset_daily_message_counts_if_needed()
    rows = sorted(
        (
            (int(user_id), int(stats.get(column, 0)))
            for user_id, stats in storage_data.get("message_stats", {}).get(str(guild_id), {}).items()
            if int(stats.get(column, 0)) > 0
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return rows if limit is None else rows[:limit]


async def blacklist_message_channel(guild_id, channel_id):
    guild_blacklist = storage_data.setdefault("message_blacklist", {}).setdefault(str(guild_id), [])
    if channel_id not in guild_blacklist:
        guild_blacklist.append(channel_id)
        guild_blacklist.sort()
        await save_storage()
    print(f"Blacklisted message channel: {channel_id}")


async def unblacklist_message_channel(guild_id, channel_id):
    guild_blacklist = storage_data.setdefault("message_blacklist", {}).setdefault(str(guild_id), [])
    if channel_id in guild_blacklist:
        guild_blacklist.remove(channel_id)
        await save_storage()
    print(f"Unblacklisted message channel: {channel_id}")


async def get_blacklisted_channels(guild_id):
    return sorted(
        int(channel_id)
        for channel_id in storage_data.get("message_blacklist", {}).get(str(guild_id), [])
    )


async def is_message_channel_blacklisted(guild_id, channel_id):
    return channel_id in storage_data.get("message_blacklist", {}).get(str(guild_id), [])


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
        "format": sticker_format or extension,
        "url": str(sticker.url),
        "filename": f"{sanitize_asset_name(sticker.name, 'stolen_sticker')}.{extension}",
    }


async def download_asset_bytes(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError("Failed to download asset.")
            return await response.read()


def convert_gif_bytes_to_apng_bytes(gif_bytes):
    try:
        from PIL import Image, ImageSequence
    except ImportError as error:
        raise ValueError("Pillow is required to convert animated stickers.") from error

    with Image.open(io.BytesIO(gif_bytes)) as image:
        frames = []
        durations = []
        loop = image.info.get("loop", 0)

        for frame in ImageSequence.Iterator(image):
            frames.append(frame.convert("RGBA"))
            durations.append(frame.info.get("duration", image.info.get("duration", 100)))

        if not frames:
            raise ValueError("No frames found in GIF sticker.")

        output = io.BytesIO()
        first_frame, *remaining_frames = frames
        first_frame.save(
            output,
            format="PNG",
            save_all=True,
            append_images=remaining_frames,
            duration=durations,
            loop=loop,
            disposal=2,
        )
        return output.getvalue()


def build_sticker_upload_files(asset_data, asset_bytes):
    sticker_format = asset_data.get("format", "").lower()
    files = [discord.File(io.BytesIO(asset_bytes), filename=asset_data["filename"])]

    if sticker_format == "gif":
        try:
            converted_bytes = convert_gif_bytes_to_apng_bytes(asset_bytes)
        except ValueError:
            return files

        filename = f"{sanitize_asset_name(asset_data['name'], 'stolen_sticker')}.png"
        files.append(discord.File(io.BytesIO(converted_bytes), filename=filename))

    return files


async def resolve_role_from_text(ctx, role_text):
    role_text = (role_text or "").strip()
    if not role_text:
        return None

    try:
        return await commands.RoleConverter().convert(ctx, role_text)
    except commands.BadArgument:
        lowered_role_text = role_text.casefold()
        for role in ctx.guild.roles:
            if role.name.casefold() == lowered_role_text:
                return role
    return None


async def resolve_role_icon_payload(icon_input):
    icon_input = (icon_input or "").strip()
    if not icon_input:
        raise ValueError("Provide an emoji for the role icon.")

    partial = discord.PartialEmoji.from_str(icon_input)
    if partial.id:
        return await download_asset_bytes(str(partial.url)), icon_input
    return icon_input, icon_input


async def parse_roleicon_inputs(ctx, raw_input):
    raw_input = (raw_input or "").strip()
    if not raw_input:
        raise ValueError("Usage: `.roleicon <role> <emoji>`")

    role = None
    icon_input = None
    parts = raw_input.split()

    for split_index in range(len(parts) - 1, 0, -1):
        candidate_role_text = " ".join(parts[:split_index])
        candidate_icon_input = " ".join(parts[split_index:])
        role = await resolve_role_from_text(ctx, candidate_role_text)
        if role is None:
            continue
        icon_input = candidate_icon_input.strip()
        if icon_input:
            return role, icon_input

    raise ValueError("Usage: `.roleicon <role> <emoji>`")


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
            upload_files = build_sticker_upload_files(self.asset_data, asset_bytes)
            last_http_error = None

            for asset_file in upload_files:
                try:
                    await guild.create_sticker(
                        name=sanitize_asset_name(self.asset_data["name"], "stolen_sticker"),
                        description="Stolen asset",
                        emoji=":)",
                        file=asset_file,
                        reason=f"Asset stolen by {interaction.user}",
                    )
                except discord.HTTPException as error:
                    last_http_error = error
                    continue
                else:
                    last_http_error = None
                    break

            if last_http_error is not None:
                raise last_http_error
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
    storage_data.setdefault("guild_settings", {})[str(guild_id)] = prefix
    await save_storage()
    print(f"Saved guild prefix for guild: {guild_id}")
    guild_prefix_cache[guild_id] = prefix


async def delete_guild_prefix(guild_id):
    storage_data.setdefault("guild_settings", {}).pop(str(guild_id), None)
    await save_storage()
    print(f"Deleted guild prefix for guild: {guild_id}")
    guild_prefix_cache.pop(guild_id, None)


async def get_guild_prefix(guild_id):
    if db is None:
        return DEFAULT_PREFIX

    return storage_data.get("guild_settings", {}).get(str(guild_id), DEFAULT_PREFIX) or DEFAULT_PREFIX


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
    if action in {"mute", "unmute", "spam_mute"}:
        return

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
        print(f"Cached {len(invites)} invites")
    except discord.Forbidden:
        print("No permission to view invites")

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
    guild_afk = storage_data.setdefault("afk_users", {}).setdefault(str(guild_id), {})
    guild_afk[str(user_id)] = {"reason": reason, "timestamp": timestamp}
    await save_storage()
    print(f"Saved AFK state for user: {user_id}")
    return cache_afk_state(guild_id, user_id, reason, timestamp)


async def get_afk_state(guild_id, user_id):
    key = afk_cache_key(guild_id, user_id)
    if key in afk_users:
        return afk_users[key]

    row = (
        storage_data.get("afk_users", {})
        .get(str(guild_id), {})
        .get(str(user_id))
    )
    if not row:
        return None
    return cache_afk_state(guild_id, user_id, row.get("reason"), row.get("timestamp"))


async def delete_afk_state(guild_id, user_id):
    afk_users.pop(afk_cache_key(guild_id, user_id), None)
    storage_data.setdefault("afk_users", {}).setdefault(str(guild_id), {}).pop(str(user_id), None)
    await save_storage()
    print(f"Deleted AFK state for user: {user_id}")


async def load_afk_users():
    afk_users.clear()
    for guild_id, guild_afk in storage_data.get("afk_users", {}).items():
        for user_id, row in guild_afk.items():
            try:
                cache_afk_state(int(guild_id), int(user_id), row.get("reason"), row.get("timestamp"))
            except (TypeError, ValueError):
                continue


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


def has_ticket_staff_access(member):
    if member.guild_permissions.administrator:
        return True

    return any(role.id == TICKET_HELPER_ROLE_ID for role in member.roles)


def member_has_role_id(member, role_id):
    return any(role.id == role_id for role in member.roles)


def can_use_command_role(member, *role_ids):
    if member.guild.owner_id == member.id:
        return True

    return any(member_has_role_id(member, role_id) for role_id in role_ids)


def can_use_no_prefix_command(member, command_name):
    if command_name == "roleicon":
        return member_has_role_id(member, OS_ROLE_ID)

    permissions = getattr(member, "guild_permissions", None)
    if permissions and (permissions.administrator or permissions.manage_guild):
        return True
    return False


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


def build_verification_panel_embed():
    embed = discord.Embed(
        title=VERIFICATION_PANEL_TITLE,
        description="This server requires you to verify yourself to get access to other channels, you can simply verify by clicking on the verify button.",
        color=discord.Color.from_str("#2b2d31"),
    )
    embed.set_image(url=VERIFICATION_PANEL_IMAGE_URL)
    return embed


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


async def send_or_update_verification_panel(channel):
    embed = build_verification_panel_embed()
    view = VerificationPanelView()
    stored_message_id = await get_state_value(VERIFICATION_PANEL_MESSAGE_KEY)
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
                if message.embeds[0].title == VERIFICATION_PANEL_TITLE:
                    await message.edit(embed=embed, view=view)
                    await set_state_value(VERIFICATION_PANEL_MESSAGE_KEY, str(message.id))
                    return message
    except (discord.Forbidden, discord.HTTPException):
        pass

    message = await channel.send(embed=embed, view=view)
    await set_state_value(VERIFICATION_PANEL_MESSAGE_KEY, str(message.id))
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


async def ensure_verification_panel():
    channel = bot.get_channel(SECURITY_VERIFICATION_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(SECURITY_VERIFICATION_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    try:
        await send_or_update_verification_panel(channel)
    except (discord.Forbidden, discord.HTTPException):
        pass


async def send_join_leave_log(guild, content):
    channel = guild.get_channel(JOIN_LEAVE_LOG_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(JOIN_LEAVE_LOG_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    try:
        await channel.send(content)
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

        ticket_helper_role = interaction.guild.get_role(TICKET_HELPER_ROLE_ID)
        if ticket_helper_role is not None:
            overwrites[ticket_helper_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
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


class VerificationPanelView(discord.ui.View):
    """Persistent verification panel."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.primary, custom_id="security_verify")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("Verification done.", ephemeral=True)
            return

        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message("Verification done.", ephemeral=True)
            return

        verified_role = interaction.guild.get_role(VERIFIED_ROLE_ID)
        unverified_role = interaction.guild.get_role(UNVERIFIED_ROLE_ID)

        if verified_role is None:
            await interaction.response.send_message("Verified role not found.", ephemeral=True)
            return

        try:
            if verified_role not in member.roles:
                await member.add_roles(verified_role, reason="Member verified through security panel")
            if unverified_role is not None and unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="Member verified through security panel")
            await ensure_peasant_role(member)
        except discord.Forbidden:
            await interaction.response.send_message("I can't update your roles.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("Verification failed.", ephemeral=True)
            return

        await interaction.response.send_message("Verification done.", ephemeral=True)


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
        if not has_ticket_staff_access(interaction.user):
            await interaction.response.send_message("Only ticket staff can use these controls.", ephemeral=True)
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


async def ensure_peasant_role(member):
    if member.bot:
        return

    verified_role = member.guild.get_role(VERIFIED_ROLE_ID)
    peasant_role = member.guild.get_role(PEASANT_ROLE_ID)
    if verified_role is None or peasant_role is None:
        return

    if verified_role not in member.roles or peasant_role in member.roles:
        return

    try:
        await member.add_roles(peasant_role, reason="Auto-assigned main member role for verified member")
    except discord.Forbidden:
        print(f"Missing permissions to assign peasant role for {member}")
    except discord.HTTPException:
        print(f"Failed to assign peasant role for {member}")


async def sync_peasant_roles_for_all_guilds():
    for guild in bot.guilds:
        verified_role = guild.get_role(VERIFIED_ROLE_ID)
        if verified_role is None:
            continue

        for member in verified_role.members:
            await ensure_peasant_role(member)


async def ensure_permission_bundle_roles(member):
    if member.bot:
        return

    source_role_ids = {role.id for role in member.roles}
    desired_target_ids = {
        target_role_id
        for source_role_id, target_role_id in DEFAULT_PERMISSION_ROLE_LINKS
        if source_role_id in source_role_ids
    }
    managed_target_ids = {target_role_id for _, target_role_id in DEFAULT_PERMISSION_ROLE_LINKS}

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

    try:
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason="Auto-assigned permission roles from staff role")
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Removed permission roles after staff role change")
    except discord.Forbidden:
        print(f"Missing permissions to sync permission bundle roles for {member}")
    except discord.HTTPException:
        print(f"Failed to sync permission bundle roles for {member}")


async def sync_permission_bundle_roles_for_all_guilds():
    for guild in bot.guilds:
        for member in guild.members:
            await ensure_permission_bundle_roles(member)


def permission_bundle_source_roles_changed(before, after):
    before_source_ids = {role.id for role in before.roles if role.id in PERMISSION_BUNDLE_SOURCE_ROLE_IDS}
    after_source_ids = {role.id for role in after.roles if role.id in PERMISSION_BUNDLE_SOURCE_ROLE_IDS}
    return before_source_ids != after_source_ids


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
    rejoins_since = datetime.now(timezone.utc) - timedelta(days=7)
    return {
        "invites": invites_count,
        "joins": await get_invite_event_count(guild_id, user_id, "join"),
        "leaves": await get_invite_event_count(guild_id, user_id, "leave"),
        "fake": await get_invite_event_count(guild_id, user_id, "fake"),
        "rejoins": await get_invite_event_count(guild_id, user_id, "rejoin", since=rejoins_since),
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
    bot.add_view(VerificationPanelView())
    await ensure_ticket_panel()
    await ensure_verification_panel()
    await sync_peasant_roles_for_all_guilds()
    # Cache all server invites
    for guild in bot.guilds:
        await cache_server_invites(guild)
    
    # Start activity rotation if not already running
    if not rotate_activity.is_running():
        rotate_activity.start()

    if not reset_daily_messages_loop.is_running():
        reset_daily_messages_loop.start()

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
    inviter_display = "Unknown"

    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role is not None and not member.bot:
        try:
            if unverified_role not in member.roles:
                await member.add_roles(unverified_role, reason="Assigned unverified role on join")
        except discord.Forbidden:
            print(f"Missing permissions to assign unverified role for {member}")
        except discord.HTTPException:
            print(f"Failed to assign unverified role for {member}")

    if not member.bot:
        verification_channel = guild.get_channel(SECURITY_VERIFICATION_CHANNEL_ID)
        if verification_channel is None:
            try:
                verification_channel = await bot.fetch_channel(SECURITY_VERIFICATION_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                verification_channel = None

        if verification_channel is not None:
            try:
                await verification_channel.send(
                    f"{member.mention} please verify here",
                    delete_after=4
                )
            except (discord.Forbidden, discord.HTTPException):
                print(f"Failed to send verification ping for {member}")

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
            inviter_display = used_invite.inviter.mention
            prior_joins_for_member = await get_user_invite_event_count(guild.id, member.id, "join")
            
            # Update database
            await add_invites(guild.id, inviter_id, 1)
            await set_inviter(guild.id, member.id, inviter_id)
            await log_invite_event(guild.id, member.id, inviter_id, "join")

            if prior_joins_for_member > 0:
                await log_invite_event(guild.id, member.id, inviter_id, "rejoin")
            
    except discord.Forbidden:
        pass
    except Exception as e:
        print(f"Error tracking invite for {member}: {e}")

    if not member.bot:
        await send_join_leave_log(
            guild,
            f"{member.mention} joined. Invited by {inviter_display}."
        )


@bot.event
async def on_member_remove(member):
    if member.bot or not member.guild:
        return

    inviter_id = await get_inviter(member.guild.id, member.id)
    inviter_display = "Unknown"
    if inviter_id:
        inviter = member.guild.get_member(inviter_id)
        if inviter is not None:
            inviter_display = inviter.mention
        else:
            inviter_display = f"<@{inviter_id}>"

    try:
        if inviter_id:
            await log_invite_event(member.guild.id, member.id, inviter_id, "leave")

            if member.joined_at is not None:
                time_in_server = datetime.now(timezone.utc) - member.joined_at
                if time_in_server <= timedelta(days=1):
                    await log_invite_event(member.guild.id, member.id, inviter_id, "fake")
    except Exception as e:
        print(f"Error tracking leave invite stats for {member}: {e}")

    await send_join_leave_log(
        member.guild,
        f"{member} left. Invited by {inviter_display}."
    )


@bot.event
async def on_member_update(before, after):
    if before.roles == after.roles:
        return

    await ensure_peasant_role(after)
    if permission_bundle_source_roles_changed(before, after):
        await ensure_permission_bundle_roles(after)


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
    vc_role_id = 1500036744970764330
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


@bot.command(name="roleicon")
async def roleicon_command(ctx, *, role_and_icon: str = None):
    """Set the icon for a role using a unicode or custom emoji."""
    if not ctx.guild:
        await ctx.send(embed=build_asset_embed("Role Icon", "This command only works in a server.", success=False))
        return

    if not member_has_role_id(ctx.author, OS_ROLE_ID):
        await ctx.send(embed=build_asset_embed("Role Icon", "You need the OS role to use this command.", success=False))
        return

    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.send(embed=build_asset_embed("Role Icon", "I need Manage Roles permission to edit role icons.", success=False))
        return

    try:
        role, icon_input = await parse_roleicon_inputs(ctx, role_and_icon)
        display_icon, display_label = await resolve_role_icon_payload(icon_input)
    except ValueError as error:
        await ctx.send(embed=build_asset_embed("Role Icon", str(error), success=False))
        return

    if role >= ctx.guild.me.top_role:
        await ctx.send(embed=build_asset_embed("Role Icon", "That role is above my highest role, so I can't edit it.", success=False))
        return

    try:
        await role.edit(
            display_icon=display_icon,
            reason=f"Role icon updated by {ctx.author} ({ctx.author.id})",
        )
    except discord.Forbidden:
        await ctx.send(embed=build_asset_embed("Role Icon", "I don't have permission to edit that role.", success=False))
        return
    except discord.HTTPException as error:
        error_text = str(error).lower()
        if "role icon" in error_text or "display icon" in error_text:
            message = "This server does not currently allow role icons, or that icon format is invalid."
        else:
            message = "I couldn't update that role icon."
        await ctx.send(embed=build_asset_embed("Role Icon", message, success=False))
        return

    await ctx.send(embed=build_asset_embed("Role Icon", f"Updated {role.mention} icon to {display_label}."))


@roleicon_command.error
async def roleicon_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_asset_embed("Role Icon", "Usage: `.roleicon <role> <emoji>`", success=False))
        return
    raise error


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
    """Temporary storage verification command"""
    if db is None:
        await ctx.send("Local storage is not initialized.")
        return

    test_key = f"dbtest:{ctx.guild.id if ctx.guild else 0}:{ctx.author.id}"
    test_value = f"ok:{int(datetime.now(timezone.utc).timestamp())}"
    await set_state_value(test_key, test_value)
    saved_value = await get_state_value(test_key)

    if saved_value == test_value:
        await ctx.send("Local storage working correctly")
        return

    await ctx.send("Local storage test failed")


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
async def warn_command(ctx, member: MemberOrID, *, reason="No reason provided"):
    """Warn a member"""
    if not can_use_command_role(ctx.author, MUTE_ROLE_ID, OS_ROLE_ID):
        await ctx.send(embed=build_moderation_embed(ctx, "Warning Failed", "You do not have the required role to use this command.", success=False))
        return

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

@bot.command(name="mute")
async def mute_command(ctx, member: MemberOrID, duration: str = "10m", *, reason="No reason provided"):
    """Mute command disabled."""
    await ctx.send(embed=build_moderation_embed(ctx, "Mute Disabled", "This bot no longer mutes members.", success=False))


async def mute_member(ctx, member: discord.Member, duration: str = "10m", reason="No reason provided"):
    """Internal mute helper disabled."""
    await ctx.send(embed=build_moderation_embed(ctx, "Mute Disabled", "This bot no longer mutes members.", success=False))


@bot.command(name="unmute")
async def unmute_command(ctx, *, target: str):
    """Unmute command disabled."""
    await ctx.send(embed=build_moderation_embed(ctx, "Unmute Disabled", "This bot no longer manages mutes.", success=False))


@unmute_command.error
async def unmute_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_moderation_embed(ctx, "Unmute Disabled", "This bot no longer manages mutes.", success=False))
        return
    raise error


@bot.command(name="kick")
async def kick_command(ctx, member: MemberOrID, *, reason="No reason provided"):
    """Kick a member from the server"""
    if not can_use_command_role(ctx.author, KICK_ROLE_ID, OS_ROLE_ID):
        await ctx.send(embed=build_moderation_embed(ctx, "Kick Failed", "You do not have the required role to use this command.", success=False))
        return

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
async def ban_command(ctx, member: MemberOrID, *, reason="No reason provided"):
    """Ban a member from the server"""
    if not can_use_command_role(ctx.author, BAN_ROLE_ID, OS_ROLE_ID):
        await ctx.send(embed=build_moderation_embed(ctx, "Ban Failed", "You do not have the required role to use this command.", success=False))
        return

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


@bot.command(name="remind")
@commands.has_permissions(manage_guild=True)
async def remind_command(ctx, *, text_and_user: str):
    """Send a manual reminder as a DM to a user by ID."""
    parts = text_and_user.rsplit(" ", 1)
    if len(parts) != 2:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Reminder",
            "Usage: `.remind <message> <user_id>`",
            success=False,
        ))
        return

    message_text, raw_target = parts
    user_id_match = re.fullmatch(r"<@!?(\d+)>|(\d+)", raw_target)
    if user_id_match is None:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Reminder",
            "Put the target user ID at the end. Example: `.remind Giveaway starting now 123456789012345678`",
            success=False,
        ))
        return

    user_id = int(user_id_match.group(1) or user_id_match.group(2))
    reminder_text = message_text.strip()
    if not reminder_text:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Reminder",
            "Reminder message cannot be empty.",
            success=False,
        ))
        return

    try:
        user = await bot.fetch_user(user_id)
    except discord.NotFound:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Reminder",
            "I could not find a Discord user with that ID.",
            success=False,
        ))
        return
    except discord.HTTPException:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Reminder",
            "I could not fetch that user right now.",
            success=False,
        ))
        return

    try:
        await user.send(reminder_text)
    except discord.Forbidden:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Reminder",
            "I found the user, but Discord is blocking DMs to them.",
            success=False,
        ))
        return
    except discord.HTTPException:
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Reminder",
            "I could not send the DM right now.",
            success=False,
        ))
        return

    await ctx.send(embed=build_automation_embed(
        ctx,
        "Reminder",
        f"Sent a DM reminder to `{user}`.",
    ))


@remind_command.error
async def remind_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=build_automation_embed(
            ctx,
            "Reminder",
            "Usage: `.remind <message> <user_id>`",
            success=False,
        ))
        return
    raise error


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
    can_run_no_prefix_command = bool(
        message.guild
        and first_word in NO_PREFIX_COMMANDS
        and can_use_no_prefix_command(message.author, first_word)
    )
    no_prefix_blocked_channel = (
        message.guild is not None
        and message.channel.id == NO_PREFIX_DISABLED_CHANNEL_ID
    )
    is_command_message = message.content.startswith(current_prefix) or (
        can_run_no_prefix_command and not no_prefix_blocked_channel
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
        if can_run_no_prefix_command:
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
            try:
                embed = discord.Embed(
                    title="🚫 Spam Detected",
                    description=f"{message.author.mention} spam message removed.",
                    color=discord.Color.orange()
                )
                await message.channel.send(embed=embed, delete_after=10)
                
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
`.mute @user [duration]` - Disabled
`.unmute @user` - Disabled
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
`.roleicon <role> <emoji>` - Change a role icon (OS only)
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
`.remind message user_id` - Ping a user with a reminder
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
✅ **Spam Protection** - Removes detected spam messages
✅ **Raid Detection** - Detects mass joins
✅ **AFK System** - Manage AFK status
✅ **Bad Word Filter** - Filters profanity
✅ **Rotating Status** - Bot status changes every 7s
✅ **Ticket System** - Support ticket management
✅ **Moderation Logs** - Track all mod actions
✅ **Role Management** - Toggle roles easily
✅ **Voice Role** - Gives a role when users join VC
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
`.mute @user [duration]` - Disabled
`.unmute @user` - Disabled
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
`.roleicon <role> <emoji>` - Change a role icon (OS only)
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
`.remind message user_id` - Ping a user with a reminder
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
✅ **Spam Protection** - Removes detected spam messages
✅ **Raid Detection** - Detects mass joins
✅ **AFK System** - Manage AFK status
✅ **Bad Word Filter** - Filters profanity
✅ **Rotating Status** - Bot status changes every 7s
✅ **Ticket System** - Support ticket management
✅ **Moderation Logs** - Track all mod actions
✅ **Role Management** - Toggle roles easily
✅ **Voice Role** - Gives a role when users join VC
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
`.mute @user [duration]` - Disabled
`.unmute @user` - Disabled
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
`.roleicon <role> <emoji>` - Change a role icon (OS only)
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
        title="SBot Setup Guide",
        color=discord.Color.green(),
        description="Here's how to set up SBot for your server:"
    )

    embed.add_field(
        name="1. Create Required Roles",
        value="Create a 'Muted' role for muting system",
        inline=False
    )

    embed.add_field(
        name="2. Create Categories",
        value="""
Create 'Tickets' category for support tickets
Create 'Temporary Channels' for temp VCs
        """,
        inline=False
    )

    embed.add_field(
        name="3. Create Ticket Panel",
        value="Use `.sendtickets` to create the ticket panel",
        inline=False
    )

    embed.set_footer(text="All set! Enjoy SBot")
    await ctx.send(embed=embed)

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

    
