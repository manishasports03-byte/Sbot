import os
import random
import json
import re
import sqlite3
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
    if not message.guild or not db_connection:
        return DEFAULT_PREFIX

    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT prefix FROM guild_settings WHERE guild_id = ?", (message.guild.id,))
        result = cursor.fetchone()
        return result[0] if result and result[0] else DEFAULT_PREFIX
    except sqlite3.Error:
        return DEFAULT_PREFIX


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=get_command_prefix, intents=intents, help_command=None)

# ===== CONFIG =====
bad_words = ["mc", "bc", "madarchod", "bhosdike", "chutiya", "idiot", "stupid"]

# ===== INVITE TRACKING CONFIG =====
INVITE_DB_FILE = "invites.db"
db_connection = None
server_invites = {}  # {guild_id: {invite_code: invite_object}}
INVITE_UI_COLOR = discord.Color.from_str("#2b2d31")
INVITED_PAGE_SIZE = 5
RESTART_NOTIFY_USER_ID = 760729575789166652
startup_notice_sent = False
MESSAGE_DAILY_RESET_KEY = "message_daily_reset_date"

# ===== ACTIVITY ROTATION =====
ACTIVITY_MESSAGES = [
    "with whAlien ✨",
    ".commands | Help Menu",
    "Serving users 🚀",
    "Made by @_anuneet1x 🤍"
]
current_activity_index = 0

# Cash tracking
CASH_DATA_FILE = "cash_data.json"
TRACKED_USER_ID = 760729575789166652
USER_WAITING_FOR_CASH = None

# ===== TEMP VC CONFIG =====
TEMP_VC_CATEGORY_NAME = "Temporary Channels"
TEMP_VC_PARENT_CHANNEL_ID = None  # Set to parent category ID if you have one
temp_vc_users = {}  # {user_id: channel_id}

# ===== TICKETS CONFIG =====
TICKET_CATEGORY_NAME = "Tickets"
TICKET_RESPONSE_CHANNEL = None  # Set if you want ticket responses in specific channel
tickets = {}  # {channel_id: {"creator": user_id, "created_at": datetime}}

# ===== GIVEAWAY CONFIG =====
giveaways = {}  # {message_id: {"message_id": int, "channel_id": int, "guild_id": int, "end_time": datetime, "winners": int, "prize": str, "ended": bool, "task": asyncio.Task | None}}

# ===== SECURITY CONFIG =====
spam_tracker = defaultdict(list)  # {user_id: [timestamps]}
SPAM_THRESHOLD = 5  # messages in SPAM_WINDOW
SPAM_WINDOW = 5  # seconds
SPAM_MUTE_DURATION = 300  # 5 minutes

# Raid detection
raid_tracker = {}  # {guild_id: {"joins": [], "started_at": datetime}}
RAID_JOIN_THRESHOLD = 10  # joins in RAID_WINDOW
RAID_WINDOW = 60  # seconds

# ===== MODERATION CONFIG =====
warnings = defaultdict(lambda: defaultdict(int))  # {guild_id: {user_id: count}}
moderation_logs = defaultdict(list)  # {guild_id: [log_entries]}

def load_cash_data():
    """Load cash history from file"""
    try:
        with open(CASH_DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_cash_data(data):
    """Save cash history to file"""
    with open(CASH_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def init_invite_database():
    """Initialize SQLite database for invite tracking"""
    global db_connection
    try:
        db_connection = sqlite3.connect(INVITE_DB_FILE)
        cursor = db_connection.cursor()
        
        # Create invite_stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invite_stats (
                guild_id INTEGER,
                user_id INTEGER,
                invites INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # Create inviter_map table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inviter_map (
                guild_id INTEGER,
                user_id INTEGER,
                inviter_id INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # Create invite_channels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invite_channels (
                guild_id INTEGER PRIMARY KEY,
                join_channel INTEGER,
                leave_channel INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_stats (
                guild_id INTEGER,
                user_id INTEGER,
                messages INTEGER DEFAULT 0,
                daily_messages INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_blacklist (
                guild_id INTEGER,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT DEFAULT '.'
            )
        """)
        
        db_connection.commit()
        print("✅ Database initialized successfully")
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")

def get_invites(guild_id, user_id):
    """Get invite count for a user"""
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT invites FROM invite_stats WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return 0

def add_invites(guild_id, user_id, amount):
    """Add invites to a user"""
    try:
        cursor = db_connection.cursor()
        current = get_invites(guild_id, user_id)
        new_total = max(0, current + amount)
        cursor.execute(
            "INSERT OR REPLACE INTO invite_stats (guild_id, user_id, invites) VALUES (?, ?, ?)",
            (guild_id, user_id, new_total)
        )
        db_connection.commit()
        return new_total
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return current

def set_inviter(guild_id, user_id, inviter_id):
    """Set who invited a user"""
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO inviter_map (guild_id, user_id, inviter_id) VALUES (?, ?, ?)",
            (guild_id, user_id, inviter_id)
        )
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def get_inviter(guild_id, user_id):
    """Get who invited a user"""
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT inviter_id FROM inviter_map WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def get_invited_users(guild_id, inviter_id):
    """Get list of users invited by someone"""
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT user_id FROM inviter_map WHERE guild_id = ? AND inviter_id = ?", (guild_id, inviter_id))
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []

def get_leaderboard(guild_id, limit=10):
    """Get top inviters for a guild"""
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT user_id, invites FROM invite_stats WHERE guild_id = ? ORDER BY invites DESC LIMIT ?",
            (guild_id, limit)
        )
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []


def get_state_value(key):
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT value FROM bot_state WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None


def set_state_value(key, value):
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO bot_state (key, value) VALUES (?, ?)",
            (key, value)
        )
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def reset_daily_message_counts_if_needed():
    today = datetime.now(timezone.utc).date().isoformat()
    last_reset = get_state_value(MESSAGE_DAILY_RESET_KEY)
    if last_reset == today:
        return

    try:
        cursor = db_connection.cursor()
        cursor.execute("UPDATE message_stats SET daily_messages = 0")
        db_connection.commit()
        set_state_value(MESSAGE_DAILY_RESET_KEY, today)
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def get_message_stats(guild_id, user_id):
    try:
        reset_daily_message_counts_if_needed()
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT messages, daily_messages FROM message_stats WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        result = cursor.fetchone()
        if result:
            return {"messages": result[0], "daily_messages": result[1]}
        return {"messages": 0, "daily_messages": 0}
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return {"messages": 0, "daily_messages": 0}


def set_message_stats(guild_id, user_id, messages, daily_messages):
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO message_stats (guild_id, user_id, messages, daily_messages)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, user_id, max(0, messages), max(0, daily_messages))
        )
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def add_messages(guild_id, user_id, amount, update_daily=False):
    stats = get_message_stats(guild_id, user_id)
    new_total = max(0, stats["messages"] + amount)
    daily_change = amount if update_daily and amount > 0 else 0
    new_daily_total = max(0, stats["daily_messages"] + daily_change)
    set_message_stats(guild_id, user_id, new_total, new_daily_total)
    return {"messages": new_total, "daily_messages": new_daily_total}


def increment_message_count(guild_id, user_id):
    stats = get_message_stats(guild_id, user_id)
    new_total = stats["messages"] + 1
    new_daily_total = stats["daily_messages"] + 1
    set_message_stats(guild_id, user_id, new_total, new_daily_total)
    return {"messages": new_total, "daily_messages": new_daily_total}


def clear_all_messages(guild_id):
    try:
        cursor = db_connection.cursor()
        cursor.execute("DELETE FROM message_stats WHERE guild_id = ?", (guild_id,))
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def reset_user_messages(guild_id, user_id):
    set_message_stats(guild_id, user_id, 0, 0)


def get_message_leaderboard(guild_id, column="messages", limit=10):
    if column not in {"messages", "daily_messages"}:
        return []

    try:
        reset_daily_message_counts_if_needed()
        cursor = db_connection.cursor()
        cursor.execute(
            f"""
            SELECT user_id, {column}
            FROM message_stats
            WHERE guild_id = ? AND {column} > 0
            ORDER BY {column} DESC
            LIMIT ?
            """,
            (guild_id, limit)
        )
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []


def blacklist_message_channel(guild_id, channel_id):
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO message_blacklist (guild_id, channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def unblacklist_message_channel(guild_id, channel_id):
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "DELETE FROM message_blacklist WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def get_blacklisted_channels(guild_id):
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT channel_id FROM message_blacklist WHERE guild_id = ? ORDER BY channel_id",
            (guild_id,)
        )
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []


def is_message_channel_blacklisted(guild_id, channel_id):
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT 1 FROM message_blacklist WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False


def set_guild_prefix(guild_id, prefix):
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO guild_settings (guild_id, prefix) VALUES (?, ?)",
            (guild_id, prefix)
        )
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def delete_guild_prefix(guild_id):
    try:
        cursor = db_connection.cursor()
        cursor.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def get_guild_prefix(guild_id):
    if not db_connection:
        return DEFAULT_PREFIX

    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT prefix FROM guild_settings WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        return result[0] if result and result[0] else DEFAULT_PREFIX
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return DEFAULT_PREFIX


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

def set_join_channel(guild_id, channel_id):
    """Set join message channel"""
    try:
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO invite_channels (guild_id, join_channel) VALUES ((SELECT guild_id FROM invite_channels WHERE guild_id = ?), ?) OR INSERT INTO invite_channels (guild_id, join_channel) VALUES (?, ?)",
            (guild_id, channel_id, guild_id, channel_id)
        )
        # Simpler approach
        cursor.execute("SELECT * FROM invite_channels WHERE guild_id = ?", (guild_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE invite_channels SET join_channel = ? WHERE guild_id = ?", (channel_id, guild_id))
        else:
            cursor.execute("INSERT INTO invite_channels (guild_id, join_channel) VALUES (?, ?)", (guild_id, channel_id))
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def set_leave_channel(guild_id, channel_id):
    """Set leave message channel"""
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT * FROM invite_channels WHERE guild_id = ?", (guild_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE invite_channels SET leave_channel = ? WHERE guild_id = ?", (channel_id, guild_id))
        else:
            cursor.execute("INSERT INTO invite_channels (guild_id, leave_channel) VALUES (?, ?)", (guild_id, channel_id))
        db_connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def get_join_channel(guild_id):
    """Get join message channel"""
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT join_channel FROM invite_channels WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def get_leave_channel(guild_id):
    """Get leave message channel"""
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT leave_channel FROM invite_channels WHERE guild_id = ?", (guild_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def extract_cash_amount(text):
    """Extract cash amount from text (e.g., '100,000' or '100000')"""
    # Look for currency patterns like: $1,234 or 1,234 or just numbers
    match = re.search(r'[\$₽]?\s*([0-9,]+(?:\.[0-9]{2})?)', text)
    if match:
        amount_str = match.group(1).replace(',', '')
        try:
            return float(amount_str)
        except ValueError:
            return None
    return None

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

def is_raid_happening(guild_id):
    """Check if raid is in progress"""
    if guild_id not in raid_tracker:
        return False
    
    data = raid_tracker[guild_id]
    now = datetime.now(timezone.utc)
    recent_joins = [t for t in data.get("joins", []) if (now - t).total_seconds() < RAID_WINDOW]
    
    return len(recent_joins) >= RAID_JOIN_THRESHOLD

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
    original_nick = member.nick
    display_name = member.display_name

    if display_name.startswith("[AFK] "):
        afk_name = display_name
    else:
        afk_name = f"[AFK] {display_name}"

    if member.id != member.guild.owner_id:
        await member.edit(nick=afk_name[:32], reason="User set AFK")

    afk_users[member.id] = {
        "nick": original_nick,
        "since": datetime.now(timezone.utc),
        "pings": [],
        "reason": reason,
    }


async def remove_afk(member):
    if member.id not in afk_users:
        return None

    afk_data = afk_users.pop(member.id)

    if member.id != member.guild.owner_id:
        await member.edit(nick=afk_data["nick"], reason="User returned from AFK")

    return afk_data


def find_role(guild, role_name):
    role_name = role_name.strip().lower()

    for role in guild.roles:
        if role.name.lower() == role_name:
            return role

    return None


async def send_restart_notice():
    message = f"<@{RESTART_NOTIFY_USER_ID}> bot is back online after the update"

    for guild in bot.guilds:
        member = guild.get_member(RESTART_NOTIFY_USER_ID)
        if not member:
            continue

        candidate_channels = []
        if guild.system_channel:
            candidate_channels.append(guild.system_channel)

        candidate_channels.extend(guild.text_channels)

        seen_channel_ids = set()
        for channel in candidate_channels:
            if channel.id in seen_channel_ids:
                continue
            seen_channel_ids.add(channel.id)

            permissions = channel.permissions_for(guild.me)
            if not permissions.send_messages:
                continue

            try:
                await channel.send(message)
                return True
            except discord.HTTPException:
                continue

    try:
        user = await bot.fetch_user(RESTART_NOTIFY_USER_ID)
        await user.send("bot is back online after the update")
        return True
    except discord.HTTPException:
        return False


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


def get_invite_ui_stats(guild_id, user_id):
    invites_count = get_invites(guild_id, user_id)
    return {
        "invites": invites_count,
        "joins": invites_count,
        "leaves": 0,
        "fake": 0,
        "rejoins": 0,
    }


def build_invites_embed(ctx, target):
    stats = get_invite_ui_stats(ctx.guild.id, target.id)
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
            title="Invited users",
            description="\n".join(
                f"#{index} • {entry}"
                for index, entry in enumerate(page_entries, start=start + 1)
            ),
            color=INVITE_UI_COLOR,
        )
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
    reset_daily_message_counts_if_needed()


@bot.event
async def on_ready():
    global startup_notice_sent
    print(f"Logged in as {bot.user}")
    
    # Initialize database
    init_invite_database()
    reset_daily_message_counts_if_needed()
    
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


# ===== MEMBER JOIN EVENT - Anti-Raid & Auto-Role =====
@bot.event
async def on_member_join(member):
    """Handle member join - check for raids, assign auto-roles, and track invites"""
    guild = member.guild

    # ===== RAID DETECTION =====
    if guild.id not in raid_tracker:
        raid_tracker[guild.id] = {"joins": [], "started_at": datetime.now(timezone.utc)}

    raid_tracker[guild.id]["joins"].append(datetime.now(timezone.utc))

    # Check if raid is happening
    if is_raid_happening(guild.id):
        print(f"⚠️ RAID DETECTED in {guild.name}! User: {member}")
        # Auto-ban if account is too new
        account_age = datetime.now(timezone.utc) - member.created_at
        if account_age.total_seconds() < 3600:  # Less than 1 hour old
            try:
                await member.ban(reason="Raid protection - new account")
                log_moderation_action(guild.id, "ban", "System", member, "Raid protection - new account")
                print(f"🛡️ Banned {member} for raid protection")
            except:
                pass

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
        
        # Track the invite
        if guild.id not in invite_stats:
            invite_stats[guild.id] = {}
            inviter_map[guild.id] = {}
        
        if used_invite and used_invite.inviter:
            # Update inviter stats
            inviter_id = used_invite.inviter.id
            
            # Update database
            add_invites(guild.id, inviter_id, 1)
            set_inviter(guild.id, member.id, inviter_id)
            
            # Send join message if configured
            join_channel_id = get_join_channel(guild.id)
            if join_channel_id:
                channel = guild.get_channel(join_channel_id)
                if channel:
                    try:
                        invites_count = get_invites(guild.id, inviter_id)
                        embed = discord.Embed(
                            title="👋 New Member Joined",
                            description=f"{member.mention} joined the server!",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Invited by", value=f"{used_invite.inviter.mention}", inline=False)
                        embed.add_field(name="Inviter's Total Invites", value=str(invites_count), inline=False)
                        embed.set_thumbnail(url=member.display_avatar.url)
                        await channel.send(embed=embed)
                    except:
                        pass
    except discord.Forbidden:
        pass
    except Exception as e:
        print(f"Error tracking invite for {member}: {e}")

    # ===== AUTO-ROLES =====
    # You can configure auto-roles by editing this section
    # Example: new_member_role = guild.get_role(ROLE_ID)
    # await member.add_roles(new_member_role)


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


@bot.command(name="serverinfo")
async def serverinfo_command(ctx):
    """Show server details"""
    guild = ctx.guild
    if not guild:
        await ctx.send("This command can only be used in a server.")
        return

    embed = discord.Embed(
        title=f"{guild.name} Server Info",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Owner", value=str(guild.owner) if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
    embed.add_field(name="Text Channels", value=str(len(guild.text_channels)), inline=True)
    embed.add_field(name="Voice Channels", value=str(len(guild.voice_channels)), inline=True)
    embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, style="F"), inline=False)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)


@bot.command(name="userinfo")
async def userinfo_command(ctx, member: discord.Member = None):
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


@bot.command(name="avatar")
async def avatar_command(ctx, member: discord.Member = None):
    """Show user's avatar"""
    target = member or ctx.author
    embed = discord.Embed(
        title=f"{target} Avatar",
        color=discord.Color.blurple()
    )
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="banner")
async def banner_command(ctx, member: discord.Member = None):
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
async def accountage_command(ctx, member: discord.Member = None):
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

    set_guild_prefix(ctx.guild.id, new_prefix)
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

    delete_guild_prefix(ctx.guild.id)
    await ctx.send(embed=discord.Embed(
        title="Prefix Reset",
        description=f"Prefix reset to `{DEFAULT_PREFIX}`",
        color=discord.Color.orange()
    ))


@bot.command(name="gstart")
@commands.has_permissions(manage_guild=True)
async def gstart_command(ctx, duration: str, winners: int, *, prize: str):
    """Start a giveaway"""
    if winners <= 0:
        await ctx.send("Winners must be at least 1.")
        return

    duration_seconds = parse_short_duration(duration)
    if duration_seconds is None:
        await ctx.send("Use a valid duration like `10m`, `1h`, or `30s`.")
        return

    end_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    embed = build_giveaway_embed(prize, winners, duration, end_time)
    giveaway_message = await ctx.send(embed=embed)

    try:
        await giveaway_message.add_reaction("🎉")
    except discord.HTTPException:
        await ctx.send("I could not add the giveaway reaction.")
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
        await ctx.send("No active giveaway found in this channel.")
        return

    if giveaway["task"] is not None:
        giveaway["task"].cancel()
        giveaway["task"] = None

    success = await finalize_giveaway(giveaway["message_id"])
    if not success:
        await ctx.send("I could not end that giveaway. The message may have been deleted.")


@bot.command(name="greroll")
@commands.has_permissions(manage_guild=True)
async def greroll_command(ctx):
    """Reroll a giveaway winner"""
    giveaway = get_latest_giveaway(ctx.channel.id, active_only=False)
    if giveaway is None:
        await ctx.send("No giveaway found in this channel.")
        return

    if not giveaway["ended"]:
        await ctx.send("That giveaway is still running. Use `.gend` first if you want to end it early.")
        return

    success = await finalize_giveaway(giveaway["message_id"], reroll=True)
    if not success:
        await ctx.send("I could not reroll that giveaway. The message may have been deleted.")


# ===== MODERATION COMMANDS =====

@bot.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def warn_command(ctx, member: discord.Member, *, reason="No reason provided"):
    """Warn a member"""
    if member == ctx.author:
        await ctx.send("You cannot warn yourself.")
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot warn someone with a higher or equal role.")
        return

    warnings[ctx.guild.id][member.id] += 1
    warn_count = warnings[ctx.guild.id][member.id]
    log_moderation_action(ctx.guild.id, "warn", ctx.author, member, reason)

    embed = discord.Embed(
        title="⚠️ Warning",
        description=f"{member.mention} has been warned.\n\nWarning Count: **{warn_count}**",
        color=discord.Color.orange()
    )
    embed.add_field(name="Reason", value=reason, inline=False)

    await ctx.send(embed=embed)

    # Auto-mute after 3 warnings
    if warn_count >= 3:
        await mute_member(ctx, member, reason="Auto-mute: 3 warnings")


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute_command(ctx, member: discord.Member, duration: str = "10m", *, reason="No reason provided"):
    """Mute a member (duration: 1m, 1h, 1d, etc.)"""
    await mute_member(ctx, member, duration, reason)


async def mute_member(ctx, member: discord.Member, duration: str = "10m", reason="No reason provided"):
    """Internal function to mute a member"""
    if member == ctx.author:
        await ctx.send("You cannot mute yourself.")
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
        
        embed = discord.Embed(
            title="🔇 Member Muted",
            description=f"{member.mention} has been muted for {duration}",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to mute this member.")


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute_command(ctx, member: discord.Member):
    """Unmute a member"""
    try:
        await member.timeout(None)
        log_moderation_action(ctx.guild.id, "unmute", ctx.author, member, "Manual unmute")
        
        embed = discord.Embed(
            title="🔊 Member Unmuted",
            description=f"{member.mention} has been unmuted",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to unmute this member.")


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_command(ctx, member: discord.Member, *, reason="No reason provided"):
    """Kick a member from the server"""
    if member == ctx.author:
        await ctx.send("You cannot kick yourself.")
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot kick someone with a higher or equal role.")
        return

    try:
        await member.kick(reason=reason)
        log_moderation_action(ctx.guild.id, "kick", ctx.author, member, reason)
        
        embed = discord.Embed(
            title="👢 Member Kicked",
            description=f"{member} has been kicked from the server",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to kick this member.")


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_command(ctx, member: discord.Member, *, reason="No reason provided"):
    """Ban a member from the server"""
    if member == ctx.author:
        await ctx.send("You cannot ban yourself.")
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot ban someone with a higher or equal role.")
        return

    try:
        await member.ban(reason=reason)
        log_moderation_action(ctx.guild.id, "ban", ctx.author, member, reason)
        
        embed = discord.Embed(
            title="🚫 Member Banned",
            description=f"{member} has been banned from the server",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("I don't have permission to ban this member.")


@bot.command(name="purge")
@commands.has_permissions(manage_messages=True)
async def purge_command(ctx, amount: int = 10):
    """Delete messages from the channel"""
    if amount < 1 or amount > 100:
        await ctx.send("Please specify between 1 and 100 messages to delete.")
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"🗑️ Deleted {len(deleted) - 1} messages.", delete_after=5)
        log_moderation_action(ctx.guild.id, "purge", ctx.author, "system", f"Deleted {len(deleted) - 1} messages")
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete messages.")


@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode_command(ctx, seconds: int = 0):
    """Set slowmode for the channel (0 to disable)"""
    if seconds < 0 or seconds > 21600:
        await ctx.send("Slowmode must be between 0 and 21600 seconds.")
        return

    try:
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send("Slowmode disabled.")
        else:
            await ctx.send(f"Slowmode set to {seconds} seconds.")
        log_moderation_action(ctx.guild.id, "slowmode", ctx.author, "channel", f"Set to {seconds}s")
    except discord.Forbidden:
        await ctx.send("I don't have permission to modify this channel.")


@bot.command(name="tickets")
async def tickets_command(ctx):
    """Show ticket creation panel"""
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description="Click the button below to create a support ticket. Our team will assist you shortly.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=TicketCreateView())


@bot.command(name="modlogs")
@commands.has_permissions(administrator=True)
async def modlogs_command(ctx, member: discord.Member = None):
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

@bot.command(name="invites", aliases=["inv"])
async def invites_command(ctx, member: discord.Member = None):
    """Show number of invites of a user"""
    target = member or ctx.author

    await ctx.send(embed=build_invites_embed(ctx, target))


@bot.command(name="inviter")
async def inviter_command(ctx, member: discord.Member = None):
    """Show who invited the user"""
    target = member or ctx.author
    
    inviter_id = get_inviter(ctx.guild.id, target.id)
    if not inviter_id:
        await ctx.send(f"Could not find who invited {target.mention}.")
        return
    
    try:
        inviter = await bot.fetch_user(inviter_id)
        embed = discord.Embed(
            title="👤 Who Invited",
            color=discord.Color.blurple()
        )
        embed.description = f"{target.mention} was invited by {inviter.mention}"
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)
    except:
        await ctx.send(f"Could not find who invited {target.mention}.")


@bot.command(name="invited")
async def invited_command(ctx, member: discord.Member = None):
    """List users invited by someone"""
    target = member or ctx.author

    invited_users = get_invited_users(ctx.guild.id, target.id)

    if not invited_users:
        await ctx.send(f"{target.mention} hasn't invited anyone.")
        return

    entries = []
    for uid in invited_users:
        try:
            user = ctx.guild.get_member(uid) or await bot.fetch_user(uid)
            entries.append(user.mention)
        except Exception:
            entries.append(f"User({uid})")

    view = InvitedUsersView(ctx.author.id, target, entries)
    message = await ctx.send(embed=view.build_embed(), view=view)
    view.message = message


@bot.command(name="inviteinfo")
async def inviteinfo_command(ctx):
    """Show all active invite links in server"""
    try:
        invites = await ctx.guild.invites()
    except discord.Forbidden:
        await ctx.send("I don't have permission to view invites.")
        return
    
    if not invites:
        await ctx.send("No active invites in this server.")
        return
    
    embed = discord.Embed(
        title="🔗 Server Invites",
        color=discord.Color.blurple()
    )
    
    for invite in invites[:10]:  # Show max 10 invites
        creator = invite.inviter.mention if invite.inviter else "Unknown"
        expires = "Never" if not invite.expires_at else invite.expires_at.strftime("%Y-%m-%d")
        embed.add_field(
            name=f"discord.gg/{invite.code}",
            value=f"👤 {creator}\n📊 Uses: {invite.uses}\n⏰ Expires: {expires}",
            inline=False
        )
    
    await ctx.send(embed=embed)


@bot.command(name="setjoinchannel")
@commands.has_permissions(administrator=True)
async def setjoinchannel_command(ctx, channel: discord.TextChannel):
    """Set channel for join messages"""
    set_join_channel(ctx.guild.id, channel.id)
    
    embed = discord.Embed(
        title="✅ Join Channel Set",
        description=f"Join messages will be sent to {channel.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.command(name="setleavechannel")
@commands.has_permissions(administrator=True)
async def setleavechannel_command(ctx, channel: discord.TextChannel):
    """Set channel for leave messages"""
    set_leave_channel(ctx.guild.id, channel.id)
    
    embed = discord.Embed(
        title="✅ Leave Channel Set",
        description=f"Leave messages will be sent to {channel.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.command(name="addinvites")
@commands.has_permissions(administrator=True)
async def addinvites_command(ctx, member: discord.Member, amount: int):
    """Add invites to a user"""
    if amount <= 0:
        await ctx.send("Please specify a positive amount.")
        return
    
    new_total = add_invites(ctx.guild.id, member.id, amount)
    
    embed = discord.Embed(
        title="➕ Invites Added",
        description=f"Added **{amount}** invite(s) to {member.mention}",
        color=discord.Color.green()
    )
    embed.add_field(name="New Total", value=str(new_total))
    await ctx.send(embed=embed)


@bot.command(name="removeinvites")
@commands.has_permissions(administrator=True)
async def removeinvites_command(ctx, member: discord.Member, amount: int):
    """Remove invites from a user"""
    if amount <= 0:
        await ctx.send("Please specify a positive amount.")
        return
    
    new_total = add_invites(ctx.guild.id, member.id, -amount)
    
    embed = discord.Embed(
        title="➖ Invites Removed",
        description=f"Removed **{amount}** invite(s) from {member.mention}",
        color=discord.Color.orange()
    )
    embed.add_field(name="New Total", value=str(new_total))
    await ctx.send(embed=embed)


@bot.command(name="messages")
async def messages_command(ctx, member: discord.Member = None):
    """Show total message count of a user"""
    target = member or ctx.author
    stats = get_message_stats(ctx.guild.id, target.id)

    embed = discord.Embed(
        title="Message Stats",
        color=discord.Color.blurple()
    )
    embed.description = (
        f"{target.mention} has sent **{stats['messages']}** message(s)\n"
        f"Daily messages: **{stats['daily_messages']}**"
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="addmessages")
@commands.has_permissions(administrator=True)
async def addmessages_command(ctx, member: discord.Member, amount: int):
    """Add messages to a user"""
    if amount <= 0:
        await ctx.send("Please specify a positive amount.")
        return

    stats = add_messages(ctx.guild.id, member.id, amount)

    embed = discord.Embed(
        title="Messages Added",
        description=f"Added **{amount}** message(s) to {member.mention}",
        color=discord.Color.green()
    )
    embed.add_field(name="New Total", value=str(stats["messages"]))
    await ctx.send(embed=embed)


@bot.command(name="removemessages")
@commands.has_permissions(administrator=True)
async def removemessages_command(ctx, member: discord.Member, amount: int):
    """Remove messages from a user"""
    if amount <= 0:
        await ctx.send("Please specify a positive amount.")
        return

    stats = add_messages(ctx.guild.id, member.id, -amount)

    embed = discord.Embed(
        title="Messages Removed",
        description=f"Removed **{amount}** message(s) from {member.mention}",
        color=discord.Color.orange()
    )
    embed.add_field(name="New Total", value=str(stats["messages"]))
    await ctx.send(embed=embed)


@bot.command(name="blacklistchannel")
@commands.has_permissions(administrator=True)
async def blacklistchannel_command(ctx, channel: discord.TextChannel):
    """Do not count messages from this channel"""
    blacklist_message_channel(ctx.guild.id, channel.id)
    await ctx.send(f"{channel.mention} has been blacklisted from message tracking.")


@bot.command(name="unblacklistchannel")
@commands.has_permissions(administrator=True)
async def unblacklistchannel_command(ctx, channel: discord.TextChannel):
    """Remove a channel from the message blacklist"""
    unblacklist_message_channel(ctx.guild.id, channel.id)
    await ctx.send(f"{channel.mention} has been removed from the message blacklist.")


@bot.command(name="blacklistedchannels")
async def blacklistedchannels_command(ctx):
    """Show all blacklisted channels"""
    channel_ids = get_blacklisted_channels(ctx.guild.id)
    if not channel_ids:
        await ctx.send("No blacklisted channels configured.")
        return

    lines = []
    for channel_id in channel_ids:
        channel = ctx.guild.get_channel(channel_id)
        lines.append(channel.mention if channel else f"Deleted Channel ({channel_id})")

    embed = discord.Embed(
        title="Blacklisted Channels",
        description="\n".join(lines),
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


@bot.command(name="clearmessages")
@commands.has_permissions(administrator=True)
async def clearmessages_command(ctx):
    """Reset all message data in server"""
    clear_all_messages(ctx.guild.id)
    await ctx.send("All message tracking data for this server has been reset.")


@bot.command(name="resetmymessages")
async def resetmymessages_command(ctx):
    """Reset own message count"""
    reset_user_messages(ctx.guild.id, ctx.author.id)
    await ctx.send(f"{ctx.author.mention}, your message count has been reset.")


@bot.command(name="leaderboard")
async def leaderboard_command(ctx, category: str = "invites"):
    """Show leaderboard stats"""
    category = category.lower()

    if category in ["invites", "inv"]:
        leaderboard = get_leaderboard(ctx.guild.id, limit=10)

        if not leaderboard:
            await ctx.send("No invite data available yet.")
            return

        embed = discord.Embed(
            title="🏆 Invite Leaderboard",
            color=discord.Color.gold()
        )

        leaderboard_text = ""
        for rank, (user_id, count) in enumerate(leaderboard, start=1):
            try:
                user = await bot.fetch_user(user_id)
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
                leaderboard_text += f"{medal} {user.mention} - **{count}** invite{'s' if count != 1 else ''}\n"
            except:
                leaderboard_text += f"#{rank} User({user_id}) - **{count}** invite{'s' if count != 1 else ''}\n"

        embed.description = leaderboard_text
        embed.set_footer(text=f"Total top inviters: {len(leaderboard)}")
        await ctx.send(embed=embed)
        return

    if category in ["messages", "dailymessages"]:
        stat_column = "messages" if category == "messages" else "daily_messages"
        leaderboard = get_message_leaderboard(ctx.guild.id, column=stat_column, limit=10)

        if not leaderboard:
            await ctx.send("No message data available yet.")
            return

        embed = discord.Embed(
            title="🏆 Message Leaderboard" if category == "messages" else "🏆 Daily Message Leaderboard",
            color=discord.Color.gold()
        )

        leaderboard_text = ""
        for rank, (user_id, count) in enumerate(leaderboard, start=1):
            try:
                user = await bot.fetch_user(user_id)
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
                leaderboard_text += f"{medal} {user.mention} - **{count}** message{'s' if count != 1 else ''}\n"
            except:
                leaderboard_text += f"#{rank} User({user_id}) - **{count}** message{'s' if count != 1 else ''}\n"

        embed.description = leaderboard_text
        embed.set_footer(text=f"Total ranked users: {len(leaderboard)}")
        await ctx.send(embed=embed)
        return

    await ctx.send("Usage: `.leaderboard invites`, `.leaderboard messages`, or `.leaderboard dailymessages`")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content.lower()
    
    # ===== SPAM DETECTION & PROTECTION =====
    if not message.author.bot and message.guild:
        if not is_message_channel_blacklisted(message.guild.id, message.channel.id):
            increment_message_count(message.guild.id, message.author.id)

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

    # Track cash for specific user
    global USER_WAITING_FOR_CASH
    
    if message.author.id == TRACKED_USER_ID and msg == "o cash":
        USER_WAITING_FOR_CASH = TRACKED_USER_ID
        return

    # Capture cash response from owo bot
    if USER_WAITING_FOR_CASH == TRACKED_USER_ID and message.author.name.lower() == "owo":
        cash_amount = extract_cash_amount(message.content)
        if cash_amount is not None:
            cash_data = load_cash_data()
            current_time = datetime.now(timezone.utc).isoformat()
            
            user_id_str = str(TRACKED_USER_ID)
            if user_id_str not in cash_data:
                cash_data[user_id_str] = []
            
            last_amount = None
            if cash_data[user_id_str]:
                last_amount = cash_data[user_id_str][-1]['amount']
            
            cash_data[user_id_str].append({
                'amount': cash_amount,
                'timestamp': current_time
            })
            save_cash_data(cash_data)
            
            # Send profit/loss message
            if last_amount is not None:
                diff = cash_amount - last_amount
                if diff > 0:
                    status = f"📈 **Profit**: +{diff:,.0f}"
                elif diff < 0:
                    status = f"📉 **Loss**: {diff:,.0f}"
                else:
                    status = "➡️ **No change**"
                
                await message.channel.send(
                    f"{message.author.mention} | Current: {cash_amount:,.0f} | {status}",
                    allowed_mentions=discord.AllowedMentions(users=False)
                )
            
            USER_WAITING_FOR_CASH = None
        return

    if bot.user in message.mentions and not message.reference:
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

    if message.guild and message.author.id in afk_users:
        afk_data = afk_users[message.author.id]
        afk_duration = format_duration(afk_data["since"])
        reason_text = format_afk_reason(afk_data.get("reason"))
        ping_summary = format_afk_pings(afk_data["pings"])

        try:
            afk_data = await remove_afk(message.author)
            afk_duration = format_duration(afk_data["since"])
            reason_text = format_afk_reason(afk_data.get("reason"))
            ping_summary = format_afk_pings(afk_data["pings"])
            await message.channel.send(
                f"Welcome back {message.author.mention}, you were AFK for {afk_duration}."
                f"{reason_text}\n"
                f"{ping_summary}"
            )
        except discord.Forbidden:
            afk_users.pop(message.author.id, None)
            await message.channel.send(
                f"Welcome back {message.author.mention}, you were AFK for {afk_duration}. "
                "I could not restore your nickname.\n"
                f"{reason_text}\n"
                f"{ping_summary}"
            )
        except discord.HTTPException:
            await message.channel.send(
                f"Welcome back {message.author.mention}, you were AFK for {afk_duration}. "
                "I could not restore your nickname right now.\n"
                f"{reason_text}\n"
                f"{ping_summary}"
            )

    for word in bad_words:
        if word in msg:
            reply = random.choice(responses)
            await message.channel.send(f"{message.author.mention} {reply}")
            break

    if message.author.id == 760729575789166652 and msg == "soja morni":
        await message.channel.send("hap \U0001f380")
        await bot.close()
        return

    for mentioned_user in message.mentions:
        if mentioned_user.id in afk_users:
            afk_data = afk_users[mentioned_user.id]
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
                title="📊 Messages Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.messages [@user]` - Show total message count
`.addmessages @user amount` - Add messages to a user
`.removemessages @user amount` - Remove messages from a user
`.blacklistchannel #channel` - Exclude a channel from tracking
`.unblacklistchannel #channel` - Remove a blacklist entry
`.blacklistedchannels` - Show blacklisted channels
`.clearmessages` - Reset all message data
`.resetmymessages` - Reset your own message count
`.leaderboard messages` - Show top message senders
`.leaderboard dailymessages` - Show top daily message senders
                """
            )
        
        elif selected == "invites":
            return discord.Embed(
                title="📨 Invite Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.invites [@user]` - Show a user's invite stats
`.inviter [@user]` - Show who invited a user
`.invited [@user]` - List users invited by someone
`.inviteinfo` - Show active invite links
`.setjoinchannel #channel` - Set the join log channel
`.unsetwelcomechannel` - Remove the join log channel
`.setleavechannel` - Set the leave log channel
`.unsetleavechannel` - Remove the leave log channel
`.setjoinmessage` - Set the join message template
`.unsetjoinmessage` - Reset the join message template
`.setleavemessage` - Set the leave message template
`.unsetleavemessage` - Reset the leave message template
`.variables` - Show available message variables
`.testmessage` - Preview the configured message
`.addinvites @user amount` - Add invites to a user
`.removeinvites @user amount` - Remove invites from a user
`.clearinvites` - Clear invite data
`.resetmyinvites` - Reset your own invites
`.leaderboard invites` - Show the invite leaderboard
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
                title="📊 Messages Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.messages [@user]` - Show total message count
`.addmessages @user amount` - Add messages to a user
`.removemessages @user amount` - Remove messages from a user
`.blacklistchannel #channel` - Exclude a channel from tracking
`.unblacklistchannel #channel` - Remove a blacklist entry
`.blacklistedchannels` - Show blacklisted channels
`.clearmessages` - Reset all message data
`.resetmymessages` - Reset your own message count
`.leaderboard messages` - Show top message senders
`.leaderboard dailymessages` - Show top daily message senders
                """
            )
        
        elif selected == "invites":
            return discord.Embed(
                title="📨 Invite Commands",
                color=discord.Color.from_str("#2b2d31"),
                description="""
`.invites [@user]` - Show a user's invite stats
`.inviter [@user]` - Show who invited a user
`.invited [@user]` - List users invited by someone
`.inviteinfo` - Show active invite links
`.setjoinchannel #channel` - Set the join log channel
`.unsetwelcomechannel` - Remove the join log channel
`.setleavechannel` - Set the leave log channel
`.unsetleavechannel` - Remove the leave log channel
`.setjoinmessage` - Set the join message template
`.unsetjoinmessage` - Reset the join message template
`.setleavemessage` - Set the leave message template
`.unsetleavemessage` - Reset the leave message template
`.variables` - Show available message variables
`.testmessage` - Preview the configured message
`.addinvites @user amount` - Add invites to a user
`.removeinvites @user amount` - Remove invites from a user
`.clearinvites` - Clear invite data
`.resetmyinvites` - Reset your own invites
`.leaderboard invites` - Show the invite leaderboard
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


@bot.command(name="help", aliases=["commands", "cmd"])
async def commands_command(ctx):
    """Show bot help and all available commands"""
    embed = get_main_help_embed()
    await ctx.send(embed=embed, view=HelpView())


@bot.command(name="setup")
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
        name="3️⃣ Set VC Role (Optional)",
        value="Edit bot.py to set your VC role ID for auto-role on voice join",
        inline=False
    )

    embed.add_field(
        name="4️⃣ Create Ticket Panel",
        value="Use `!tickets` to create a ticket panel",
        inline=False
    )

    embed.add_field(
        name="5️⃣ Configure Welcome",
        value="Set up welcome channel and auto-roles in bot configuration",
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
