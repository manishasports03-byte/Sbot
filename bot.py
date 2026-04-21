import os
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

bad_words = ["mc", "bc", "madarchod", "bhosdike", "chutiya", "idiot", "stupid"]

responses = [
    "bhai chill kar \U0001f602",
    "itna gussa kyu \U0001f62d",
    "language control bro \U0001f624",
    "cool banne ki koshish fail \U0001f480",
    "admin bulaun kya \U0001f440",
]

afk_users = {}
MAX_AFK_PINGS_TO_SHOW = 5

# Coin flip tracking
MAX_FLIP_RESULTS = 25
OWO_BOT_ID = 408785106942164992

# Database setup
DB_PATH = Path("coin_flips.db")

def init_db():
    """Initialize the coin flip database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coin_flips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_flip_count():
    """Get total number of flips recorded in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM coin_flips")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def add_flip_to_db(result):
    """Add a coin flip result to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO coin_flips (result) VALUES (?)", (result.lower(),))
    conn.commit()
    conn.close()

def get_last_25_flips():
    """Get the last 25 flips from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT result FROM coin_flips ORDER BY id DESC LIMIT 25")
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return list(reversed(results))  # Return in chronological order


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
    guild_id = ctx.guild.id if ctx.guild else "DM"
    embed = discord.Embed(title=f"{bot.user.display_name} Info", color=discord.Color.dark_gray())
    embed.description = (
        "Hey, I'm here to help with server utilities.\n\n"
        "**Guild Settings**\n"
        "Prefix : `!`\n"
        "Language : Eng\n"
        f"Server Id : `{guild_id}`\n\n"
        "Made with \u2764 by @_anuneet1x"
    )

    if bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    await ctx.send(embed=embed, view=BotInfoView())


class BotInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        permissions = discord.Permissions(
            send_messages=True,
            embed_links=True,
            manage_nicknames=True,
            manage_roles=True,
        )
        invite_url = discord.utils.oauth_url(bot.user.id, permissions=permissions)
        support_url = os.getenv("SUPPORT_URL", "https://discord.com")
        vote_url = os.getenv("VOTE_URL", "https://discord.com")

        self.add_item(discord.ui.Button(label="Invite", url=invite_url))
        self.add_item(discord.ui.Button(label="Support", url=support_url))
        self.add_item(discord.ui.Button(label="Vote", url=vote_url))


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
    guild_id = ctx.guild.id if ctx.guild else "DM"
    embed = discord.Embed(
        title="poyoyoi Utility Bot",
        color=discord.Color.dark_gray(),
    )
    embed.description = (
        "Hey, I'm a utility bot for your server.\n\n"
        "**Guild Settings**\n"
        "Prefix : `!`\n"
        "Language : Eng\n"
        f"Server Id : `{guild_id}`\n\n"
        "Made with \u2764 by @_anuneet1x"
    )

    if bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    await ctx.send(embed=embed, view=LunexaView())


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


async def read_owo_coin_flips(channel):
    """Read recent coin flip results from OWO bot messages in the channel."""
    owo_results = []
    try:
        # Read last 100 messages from channel
        async for message in channel.history(limit=100):
            if message.author.id == OWO_BOT_ID:
                content = message.content.lower()
                # Check for heads or tails in the message
                if "heads" in content:
                    owo_results.append("heads")
                elif "tails" in content:
                    owo_results.append("tails")
                
                # Stop when we have enough data
                if len(owo_results) >= 50:
                    break
    except discord.Forbidden:
        return None
    except Exception as e:
        print(f"Error reading OWO messages: {e}")
        return None
    
    return list(reversed(owo_results))  # Return in chronological order


async def sync_flips_from_owo(channel):
    """Sync coin flip data from OWO bot if database is empty."""
    if get_flip_count() == 0:
        owo_flips = await read_owo_coin_flips(channel)
        if owo_flips:
            for flip in owo_flips[:MAX_FLIP_RESULTS]:
                add_flip_to_db(flip)


def analyze_coin_flip_probability():
    """Analyze the last 25 flips and predict the next outcome."""
    flips = get_last_25_flips()
    
    if not flips:
        return None
    
    heads_count = flips.count("heads")
    tails_count = flips.count("tails")
    total = len(flips)
    
    heads_prob = (heads_count / total) * 100
    tails_prob = (tails_count / total) * 100
    
    # Predict based on which is more likely
    predicted = "heads" if heads_prob > tails_prob else "tails"
    confidence = abs(heads_prob - tails_prob)
    
    return {
        "heads_count": heads_count,
        "tails_count": tails_count,
        "total": total,
        "heads_prob": heads_prob,
        "tails_prob": tails_prob,
        "predicted": predicted,
        "confidence": confidence,
    }


@bot.command(name="cf")
async def coin_flip_command(ctx):
    """Flip a coin using OWO bot data and predict."""
    try:
        # Sync OWO data if database is empty
        await sync_flips_from_owo(ctx.channel)
        
        flip_count = get_flip_count()
        
        # First 25 flips: Just show data saved message
        if flip_count < MAX_FLIP_RESULTS:
            flips = get_last_25_flips()
            add_flip_to_db(random.choice(["heads", "tails"]))
            
            embed = discord.Embed(
                title="Coin Flip Data Collection",
                color=discord.Color.gold(),
                description=f"Data Saved! ({flip_count + 1}/{MAX_FLIP_RESULTS})"
            )
            
            if flips:
                results_display = " ".join([f"{'H' if r == 'heads' else 'T'}" for r in flips])
                embed.add_field(
                    name="Current Data",
                    value=f"`{results_display}`\n(H = Heads, T = Tails)",
                    inline=False
                )
                embed.set_footer(text=f"Once we reach {MAX_FLIP_RESULTS} flips, predictions will start!")
            
            await ctx.send(embed=embed)
        else:
            # After 25 flips: Show prediction
            add_flip_to_db(random.choice(["heads", "tails"]))
            analysis = analyze_coin_flip_probability()
            
            embed = discord.Embed(
                title="Coin Flip Prediction",
                color=discord.Color.gold(),
                description=f"Based on last {analysis['total']} flips"
            )
            
            embed.add_field(
                name="Statistics",
                value=f"Heads: **{analysis['heads_count']}** ({analysis['heads_prob']:.1f}%)\n"
                      f"Tails: **{analysis['tails_count']}** ({analysis['tails_prob']:.1f}%)",
                inline=False
            )
            
            embed.add_field(
                name="Prediction",
                value=f"**Next Likely: {analysis['predicted'].upper()}**\n"
                      f"Confidence: {analysis['confidence']:.1f}%",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
    except Exception as e:
        await ctx.send(f"Error processing coin flip: {str(e)}")


@bot.command(name="cfpredict")
async def coin_flip_predict_command(ctx):
    """Analyze and predict based on current database."""
    flip_count = get_flip_count()
    
    if flip_count < MAX_FLIP_RESULTS:
        await ctx.send(f"Not enough data yet! Need {MAX_FLIP_RESULTS} flips to predict. Current: {flip_count}/{MAX_FLIP_RESULTS}")
        return
    
    analysis = analyze_coin_flip_probability()
    
    embed = discord.Embed(
        title="Coin Flip Probability Analysis",
        color=discord.Color.blue(),
    )
    
    embed.add_field(
        name="Data from Last Flips",
        value=f"Total Flips: **{analysis['total']}**\n"
              f"Heads: **{analysis['heads_count']}** ({analysis['heads_prob']:.1f}%)\n"
              f"Tails: **{analysis['tails_count']}** ({analysis['tails_prob']:.1f}%)",
        inline=False
    )
    
    embed.add_field(
        name="Prediction",
        value=f"**Predicted Outcome: {analysis['predicted'].upper()}**\n"
              f"Confidence: {analysis['confidence']:.1f}%",
        inline=False
    )
    
    embed.set_footer(text="Note: This is based on recent patterns and not guaranteed!")
    
    await ctx.send(embed=embed)


@bot.command(name="cfstats")
async def coin_flip_stats_command(ctx):
    """Display the full history of recent coin flips."""
    flips = get_last_25_flips()
    
    if not flips:
        await ctx.send("No flip data yet! Use `!cf` to start collecting data.")
        return
    
    # Create a nice display of results
    results_display = " ".join([f"{'H' if r == 'heads' else 'T'}" for r in flips])
    
    analysis = analyze_coin_flip_probability()
    
    embed = discord.Embed(
        title="Coin Flip History",
        color=discord.Color.purple(),
    )
    
    embed.add_field(
        name="Last 25 Flips",
        value=f"`{results_display}`\n(H = Heads, T = Tails)",
        inline=False
    )
    
    embed.add_field(
        name="Summary",
        value=f"Heads: **{analysis['heads_count']}** ({analysis['heads_prob']:.1f}%)\n"
              f"Tails: **{analysis['tails_count']}** ({analysis['tails_prob']:.1f}%)",
        inline=False
    )
    
    await ctx.send(embed=embed)


@bot.command(name="cfclear")
async def coin_flip_clear_command(ctx):
    """Clear all coin flip data (admin only)."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Only admins can clear flip data.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM coin_flips")
    conn.commit()
    conn.close()
    
    await ctx.send("Coin flip data cleared!")


@bot.command(name="cfstatus")
async def coin_flip_status_command(ctx):
    """Check the current coin flip database status."""
    flip_count = get_flip_count()
    
    embed = discord.Embed(
        title="Coin Flip System Status",
        color=discord.Color.green(),
    )
    
    embed.add_field(
        name="Data Collected",
        value=f"{flip_count}/{MAX_FLIP_RESULTS} flips",
        inline=False
    )
    
    if flip_count >= MAX_FLIP_RESULTS:
        embed.add_field(
            name="Status",
            value="✅ Prediction mode ACTIVE\nUse `!cfpredict` to see predictions!",
            inline=False
        )
    else:
        embed.add_field(
            name="Status",
            value=f"🔄 Collection mode\nNeed {MAX_FLIP_RESULTS - flip_count} more flips to activate predictions!",
            inline=False
        )
    
    await ctx.send(embed=embed)


@bot.command(name="cfsync")
async def coin_flip_sync_command(ctx):
    """Manually sync coin flip data from OWO bot messages."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Only admins can sync OWO data.")
        return
    
    async with ctx.typing():
        owo_flips = await read_owo_coin_flips(ctx.channel)
        
        if not owo_flips:
            await ctx.send("❌ Could not read OWO bot messages. Make sure the OWO bot has sent messages in this channel.")
            return
        
        # Count how many new flips we would add
        current_count = get_flip_count()
        flips_to_add = min(len(owo_flips), MAX_FLIP_RESULTS - current_count)
        
        if flips_to_add > 0:
            for flip in owo_flips[:flips_to_add]:
                add_flip_to_db(flip)
        
        embed = discord.Embed(
            title="OWO Data Sync Complete",
            color=discord.Color.green(),
        )
        
        embed.add_field(
            name="Results",
            value=f"Found: {len(owo_flips)} OWO flips\n"
                  f"Added: {flips_to_add} new flips\n"
                  f"Total in DB: {get_flip_count()}/{MAX_FLIP_RESULTS}",
            inline=False
        )
        
        await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    guild = member.guild
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


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content.lower()

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


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set. Add it to .env before starting the bot.")

bot.run(token)
