import os
import random
import json
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import asyncio

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

# ===== CONFIG =====
bad_words = ["mc", "bc", "madarchod", "bhosdike", "chutiya", "idiot", "stupid"]

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
    embed = discord.Embed(color=discord.Color.from_rgb(88, 101, 242))
    embed.title = "Hey, I'm whAlien"
    
    embed.add_field(name="Server Prefix:", value="`.`", inline=False)
    embed.add_field(name="Get Started:", value="Run `.commands` to discover all features", inline=False)
    embed.add_field(name="Support:", value="Having issues ? Join our Support Server", inline=False)

    if bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.set_footer(text="Powered by guddu mistri")
    await ctx.send(embed=embed, view=WhAlienInfoView())


class WhAlienInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        support_url = os.getenv("SUPPORT_URL", "https://discord.com")

        self.add_item(discord.ui.Button(label="Features", style=discord.ButtonStyle.blurple, url=support_url))
        self.add_item(discord.ui.Button(label="Support Server", style=discord.ButtonStyle.blurple, url=support_url))


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
    embed = discord.Embed(color=discord.Color.from_rgb(88, 101, 242))
    embed.title = "Hey, I'm whAlien"
    
    embed.add_field(name="Server Prefix:", value="`.`", inline=False)
    embed.add_field(name="Get Started:", value="Run `.commands` to discover all features", inline=False)
    embed.add_field(name="Support:", value="Having issues ? Join our Support Server", inline=False)

    if bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.set_footer(text="Powered by guddu mistri")
    await ctx.send(embed=embed, view=WhAlienInfoView())


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


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


# ===== MEMBER JOIN EVENT - Anti-Raid & Auto-Role =====
@bot.event
async def on_member_join(member):
    """Handle member join - check for raids and assign auto-roles"""
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


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content.lower()
    
    # ===== SPAM DETECTION & PROTECTION =====
    if not message.author.bot and message.guild:
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

@bot.command(name="commands", aliases=["cmd"])
async def commands_command(ctx):
    """Show bot help and all available commands"""
    embed = discord.Embed(
        title="📚 SBot Commands",
        color=discord.Color.blue(),
        description="Here are all available commands:"
    )

    # Moderation
    embed.add_field(
        name="🛡️ Moderation Commands",
        value="""
`.warn @user [reason]` - Warn a member
`.mute @user [duration]` - Mute a member (e.g., 10m, 1h)
`.unmute @user` - Unmute a member
`.kick @user [reason]` - Kick a member
`.ban @user [reason]` - Ban a member
`.purge [amount]` - Delete messages
`.slowmode [seconds]` - Set channel slowmode
        """,
        inline=False
    )

    # Tickets & Utilities
    embed.add_field(
        name="🎫 Tickets & Utilities",
        value="""
`.tickets` - Show ticket creation panel
`.modlogs [@user]` - View moderation logs
`.afk [reason]` - Go AFK
`.role @user Role Name` - Toggle role
        """,
        inline=False
    )

    # Info
    embed.add_field(
        name="ℹ️ Info Commands",
        value="`about` or `.info` - Bot information\n`.commands` - Show all commands",
        inline=False
    )

    embed.add_field(
        name="🔧 Features",
        value="""
✅ AFK System
✅ Role Management  
✅ Moderation Tools
✅ Ticket System
✅ Temporary Voice Channels
✅ Spam Protection
✅ Raid Detection
✅ Moderation Logs
✅ Auto-mute on warnings
        """,
        inline=False
    )

    embed.set_footer(text="Use .commands to see all commands | Made with ❤️ by guddu mistri | Prefix: .")
    await ctx.send(embed=embed)


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
    embed = discord.Embed(
        title="📊 SBot Statistics",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🖥️ Server Info",
        value=f"Members: {ctx.guild.member_count}\nChannels: {len(ctx.guild.channels)}",
        inline=False
    )

    embed.add_field(
        name="📋 Moderation",
        value=f"Warnings: {sum(len(users) for users in warnings.get(ctx.guild.id, {}).values())}\nLogs: {len(moderation_logs.get(ctx.guild.id, []))}",
        inline=False
    )

    embed.add_field(
        name="🎫 Tickets",
        value=f"Open Tickets: {len(tickets)}\nTotal Created: {sum(1 for t in tickets.values() if t['created_at'])}",
        inline=False
    )

    await ctx.send(embed=embed)


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set. Add it to .env before starting the bot.")

bot.run(token)
