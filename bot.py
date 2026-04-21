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
MAX_FLIP_RESULTS = 20
OWO_BOT_ID = 408785106942164992
cf_channel_id = None  # Channel where CF system is active
cf_listening = False  # Whether system is listening for OWO results
owo_message_tracking = {}  # Track OWO messages: {message_id: chosen_value}

# Database setup
DB_PATH = Path("coin_flips.db")

def init_db():
    """Initialize the coin flip database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coin_flips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chosen TEXT NOT NULL,
            result TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flip_number INTEGER NOT NULL,
            predicted TEXT NOT NULL,
            actual TEXT,
            is_correct BOOLEAN,
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

def add_flip_to_db(chosen, result):
    """Add a coin flip with chosen value and result to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO coin_flips (chosen, result) VALUES (?, ?)", 
        (chosen.lower(), result.lower())
    )
    conn.commit()
    conn.close()

def get_last_25_flips():
    """Get the last 25 flips from database with chosen and result."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT chosen, result FROM coin_flips ORDER BY id DESC LIMIT 25")
    results = cursor.fetchall()
    conn.close()
    return list(reversed(results))  # Return in chronological order

def clear_all_data():
    """Clear all coin flip and prediction data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM coin_flips")
    cursor.execute("DELETE FROM predictions")
    conn.commit()
    conn.close()

def add_prediction(flip_number, predicted):
    """Add a prediction to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO predictions (flip_number, predicted) VALUES (?, ?)",
        (flip_number, predicted.lower())
    )
    conn.commit()
    conn.close()

def get_last_prediction():
    """Get the last prediction made."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, flip_number, predicted FROM predictions ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result

def update_prediction(prediction_id, actual_result):
    """Update prediction with actual result and mark if correct."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT predicted FROM predictions WHERE id = ?",
        (prediction_id,)
    )
    prediction = cursor.fetchone()
    is_correct = prediction[0] == actual_result.lower() if prediction else False
    
    cursor.execute(
        "UPDATE predictions SET actual = ?, is_correct = ? WHERE id = ?",
        (actual_result.lower(), is_correct, prediction_id)
    )
    conn.commit()
    conn.close()
    return is_correct

def get_prediction_accuracy():
    """Get prediction accuracy stats."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM predictions WHERE is_correct = 1")
    correct = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM predictions WHERE actual IS NOT NULL")
    total = cursor.fetchone()[0]
    conn.close()
    
    if total == 0:
        return 0, 0
    return correct, total


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


def analyze_coin_flip_probability(flips=None):
    """Analyze which CHOICE leads to more WINS, then predict that choice."""
    if flips is None:
        flips = get_last_25_flips()
    
    if not flips:
        return None
    
    # Separate by choice and count wins/losses for each
    heads_flips = [flip for flip in flips if flip[0] == "heads"]
    tails_flips = [flip for flip in flips if flip[0] == "tails"]
    
    # Count wins for each choice
    heads_wins = sum(1 for flip in heads_flips if flip[1] == "won")
    heads_total = len(heads_flips)
    heads_win_rate = (heads_wins / heads_total * 100) if heads_total > 0 else 0
    
    tails_wins = sum(1 for flip in tails_flips if flip[1] == "won")
    tails_total = len(tails_flips)
    tails_win_rate = (tails_wins / tails_total * 100) if tails_total > 0 else 0
    
    # Predict the choice with HIGHER WIN RATE
    predicted = "heads" if heads_win_rate >= tails_win_rate else "tails"
    confidence = abs(heads_win_rate - tails_win_rate)
    
    return {
        "heads_wins": heads_wins,
        "heads_total": heads_total,
        "heads_win_rate": heads_win_rate,
        "tails_wins": tails_wins,
        "tails_total": tails_total,
        "tails_win_rate": tails_win_rate,
        "predicted": predicted,
        "confidence": confidence,
        "total": len(flips),
    }


def get_all_flips():
    """Get all flips from database for pattern analysis."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT chosen FROM coin_flips ORDER BY id ASC")
    results = cursor.fetchall()
    conn.close()
    return [flip[0][0].upper() for flip in results]  # Return H or T


def analyze_sequence_patterns(sequence_length=3):
    """Analyze repeating patterns in chosen sequence."""
    choices = get_all_flips()
    
    if len(choices) < sequence_length:
        return None
    
    # Extract all N-grams
    sequences = {}
    for i in range(len(choices) - sequence_length + 1):
        pattern = "".join(choices[i:i + sequence_length])
        if pattern not in sequences:
            sequences[pattern] = {"count": 0, "follows": {}}
        sequences[pattern]["count"] += 1
        
        # Track what comes after this pattern
        if i + sequence_length < len(choices):
            next_choice = choices[i + sequence_length]
            sequences[pattern]["follows"][next_choice] = sequences[pattern]["follows"].get(next_choice, 0) + 1
    
    return sequences


def get_pattern_prediction():
    """Predict next flip based on sequence patterns."""
    choices = get_all_flips()
    
    if len(choices) < 3:
        return None
    
    # Get current pattern (last 3 flips)
    current_pattern = "".join(choices[-3:])
    
    # Analyze all sequences to find pattern
    sequences = analyze_sequence_patterns(3)
    
    if current_pattern not in sequences:
        return None
    
    pattern_data = sequences[current_pattern]
    
    if not pattern_data["follows"]:
        return None
    
    # Find which continuation is most frequent
    most_common = max(pattern_data["follows"].items(), key=lambda x: x[1])
    predicted_choice = most_common[0]
    frequency = most_common[1]
    
    # Calculate confidence as percentage
    total_continuations = sum(pattern_data["follows"].values())
    confidence = (frequency / total_continuations) * 100
    
    return {
        "pattern": current_pattern,
        "predicted": predicted_choice,
        "frequency": frequency,
        "total": total_continuations,
        "confidence": confidence,
        "pattern_count": pattern_data["count"],
    }


def predict_next_outcome():
    """Predict next actual coin outcome (not choice) based on won/lost results."""
    flips = get_last_25_flips()

    if len(flips) < 10:
        return "Not enough data", 0

    # Extract actual outcomes based on results
    # If WON → actual outcome matched what was chosen
    # If LOST → actual outcome was opposite of chosen
    outcomes = []

    for chosen, result in flips:
        if result == "won":
            outcomes.append("H" if chosen == "heads" else "T")
        else:
            outcomes.append("T" if chosen == "heads" else "H")

    # Count last 10 outcomes
    recent = outcomes[-10:]
    heads = recent.count("H")
    tails = recent.count("T")

    total = len(recent)

    if heads > tails:
        return "HEADS", round(heads/total*100, 2)
    else:
        return "TAILS", round(tails/total*100, 2)


@bot.command(name="cf")
async def coin_flip_command(ctx):
    """Start/reset coin flip prediction system."""
    global cf_channel_id, cf_listening
    
    # Clear all previous data
    clear_all_data()
    cf_channel_id = ctx.channel.id
    cf_listening = True
    
    embed = discord.Embed(
        title="🪙 Coin Flip Prediction System Started",
        color=discord.Color.gold(),
        description="System is ready! Use OWO bot to flip coins 25 times.\n\n"
                    f"Waiting for 25 results from <@{OWO_BOT_ID}>..."
    )
    
    embed.add_field(
        name="Progress",
        value="0/25 flips recorded",
        inline=False
    )
    
    embed.set_footer(text="The bot will auto-detect OWO results and track them")
    await ctx.send(embed=embed)


@bot.command(name="cfstop")
async def coin_flip_stop_command(ctx):
    """Stop the coin flip prediction system."""
    global cf_listening
    cf_listening = False
    await ctx.send("Coin flip system stopped.")


@bot.command(name="cftest")
async def coin_flip_test_command(ctx):
    """Test if the system is listening."""
    global cf_listening, cf_channel_id, owo_message_tracking
    
    embed = discord.Embed(
        title="Coin Flip System Status",
        color=discord.Color.blue(),
    )
    
    embed.add_field(
        name="Listening",
        value="✅ YES" if cf_listening else "❌ NO",
        inline=False
    )
    
    embed.add_field(
        name="Channel ID",
        value=f"{cf_channel_id or 'Not Set'} (Current: {ctx.channel.id})",
        inline=False
    )
    
    embed.add_field(
        name="Tracked Messages",
        value=f"{len(owo_message_tracking)} awaiting result",
        inline=False
    )
    
    embed.add_field(
        name="Data Count",
        value=f"{get_flip_count()}/25",
        inline=False
    )
    
    await ctx.send(embed=embed)


@bot.command(name="cfstats")
async def coin_flip_stats_command(ctx):
    """Display current statistics and predictions."""
    flip_count = get_flip_count()
    
    if flip_count == 0:
        await ctx.send("No flip data yet! Use `!cf` to start the system.")
        return
    
    flips = get_last_25_flips()
    
    # Create display showing chosen vs result
    results_display = " ".join([f"{'H' if flip[0] == 'heads' else 'T'}" for flip in flips])
    chosen_display = " ".join([f"{'W' if flip[1] == 'won' else 'L'}" for flip in flips])
    
    embed = discord.Embed(
        title="Coin Flip Statistics",
        color=discord.Color.purple(),
    )
    
    embed.add_field(
        name="Flips Recorded",
        value=f"{flip_count} flips",
        inline=False
    )
    
    if flip_count >= MAX_FLIP_RESULTS:
        embed.add_field(
            name="Last 25 Chosen",
            value=f"`{results_display}`\n(H = Heads, T = Tails)",
            inline=False
        )
        embed.add_field(
            name="Last 25 Results",
            value=f"`{chosen_display}`\n(W = Won, L = Lost)",
            inline=False
        )
        
        analysis = analyze_coin_flip_probability()
        embed.add_field(
            name="Win Rate Analysis",
            value=f"**Heads**: {analysis['heads_wins']}/{analysis['heads_total']} wins ({analysis['heads_win_rate']:.1f}%)\n"
                  f"**Tails**: {analysis['tails_wins']}/{analysis['tails_total']} wins ({analysis['tails_win_rate']:.1f}%)",
            inline=False
        )
        embed.add_field(
            name="Prediction",
            value=f"**{analysis['predicted'].upper()}** recommended (higher win rate)\nConfidence: {analysis['confidence']:.1f}%",
            inline=False
        )
        embed.add_field(
            name="Current Progress",
            value=f"Recording: {flip_count}/{MAX_FLIP_RESULTS}\n"
                  f"Chosen: `{results_display}`\n"
                  f"Results: `{chosen_display}`",
            inline=False
        )
        embed.set_footer(text=f"Need {MAX_FLIP_RESULTS - flip_count} more flips for predictions")
    
    # Show predictions accuracy if any
    correct, total = get_prediction_accuracy()
    if total > 0:
        accuracy = (correct / total) * 100
        embed.add_field(
            name="Prediction Accuracy",
            value=f"{correct}/{total} predictions correct ({accuracy:.1f}%)",
            inline=False
        )
    
    await ctx.send(embed=embed)


@bot.command(name="cfpredict")
async def coin_flip_pattern_predict_command(ctx):
    """Display pattern-based prediction for next flip."""
    flip_count = get_flip_count()
    
    if flip_count < 3:
        await ctx.send("Need at least 3 flips of data for pattern analysis!")
        return
    
    pattern_pred = get_pattern_prediction()
    
    if not pattern_pred:
        await ctx.send("Not enough pattern data yet. Keep flipping!")
        return
    
    choices = get_all_flips()
    current_sequence = "".join(choices[-3:])
    
    embed = discord.Embed(
        title="🔍 Pattern-Based Prediction",
        color=discord.Color.orange(),
    )
    
    embed.add_field(
        name="Current Sequence",
        value=f"`{current_sequence}`\n(Last 3 flips)",
        inline=False
    )
    
    embed.add_field(
        name="Pattern Analysis",
        value=f"Pattern `{pattern_pred['pattern']}` has appeared **{pattern_pred['pattern_count']}** times",
        inline=False
    )
    
    embed.add_field(
        name="Continuation Frequency",
        value=f"When `{pattern_pred['pattern']}` appears:\n"
              f"• **{pattern_pred['predicted']}**: {pattern_pred['frequency']} times\n"
              f"• Total continuations: {pattern_pred['total']}",
        inline=False
    )
    
    embed.add_field(
        name="Prediction",
        value=f"**Predict: {pattern_pred['predicted'].upper()}**\nBased on sequence pattern\nConfidence: {pattern_pred['confidence']:.1f}%",
        inline=False
    )
    
    # Also show win-rate prediction for comparison
    if flip_count >= MAX_FLIP_RESULTS:
        win_rate_pred = analyze_coin_flip_probability()
        embed.add_field(
            name="Comparison",
            value=f"**Win-Rate Prediction**: {win_rate_pred['predicted'].upper()} ({win_rate_pred['confidence']:.1f}%)\n"
                  f"**Pattern Prediction**: {pattern_pred['predicted'].upper()} ({pattern_pred['confidence']:.1f}%)",
            inline=False
        )
    
    await ctx.send(embed=embed)


@bot.command(name="cfoutcome")
async def predict_outcome_command(ctx):
    """Predict next actual coin outcome based on won/lost results."""
    pred, conf = predict_next_outcome()

    embed = discord.Embed(
        title="🎯 Outcome Prediction",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Next Flip Likely Outcome",
        value=f"**{pred}**",
        inline=False
    )

    embed.add_field(
        name="Confidence",
        value=f"{conf}%",
        inline=False
    )

    embed.set_footer(text="Based on actual coin outcomes (not your choices)")
    await ctx.send(embed=embed)


@bot.command(name="cfclear")
async def coin_flip_clear_command(ctx):
    """Clear all coin flip data (admin only)."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("Only admins can clear flip data.")
        return
    
    clear_all_data()
    await ctx.send("All coin flip data cleared!")


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

    # Coin flip prediction system - listen for OWO bot messages
    global cf_listening, cf_channel_id, owo_message_tracking
    
    # Auto-start system if OWO coin flip detected and not already listening
    if message.author.id == OWO_BOT_ID:
        msg_lower = message.content.lower()
        if ("chose" in msg_lower and ("heads" in msg_lower or "tails" in msg_lower)) or ("and you won" in msg_lower or "lost it all" in msg_lower):
            # This looks like a coin flip message - auto-start if not running
            if not cf_listening:
                cf_listening = True
                cf_channel_id = message.channel.id
                clear_all_data()  # Start fresh
                print(f"[CF AUTO-START] System started in channel {message.channel.id}")
    
    if cf_listening and message.author.id == OWO_BOT_ID and message.channel.id == cf_channel_id:
        msg_lower = message.content.lower()
        chosen = None
        result = None
        
        # Debug: Log all OWO messages in the channel
        print(f"[OWO MESSAGE] Full: {message.content}")
        
        # Check for "chose heads/tails"
        if "heads" in msg_lower and "chose" in msg_lower:
            chosen = "heads"
            print(f"[CF CHOSE] Detected HEADS")
        elif "tails" in msg_lower and "chose" in msg_lower:
            chosen = "tails"
            print(f"[CF CHOSE] Detected TAILS")
        
        # Check for result in same message (won/lost) - be specific to avoid emoji matching
        # Look for "and you won" or "and you lost" or "lost it all"
        if "and you lost" in msg_lower or "lost it all" in msg_lower:
            result = "lost"
            print(f"[CF RESULT] Detected LOST (initial message)")
        elif "and you won" in msg_lower:
            result = "won"
            print(f"[CF RESULT] Detected WON (initial message)")
        
        # If we have BOTH chosen and result, save immediately
        if chosen and result:
            flip_count = get_flip_count()
            add_flip_to_db(chosen, result)
            new_flip_count = get_flip_count()
            
            print(f"[CF SAVED] Flip {new_flip_count}/{MAX_FLIP_RESULTS} - {chosen} + {result}")
            
            # First 20 flips - just collect data
            if new_flip_count <= MAX_FLIP_RESULTS:
                flips = get_last_25_flips()
                chosen_display = " ".join([f"{'H' if flip[0] == 'heads' else 'T'}" for flip in flips])
                result_display = " ".join([f"{'W' if flip[1] == 'won' else 'L'}" for flip in flips])
                
                embed = discord.Embed(
                    title="✅ Data Saved",
                    color=discord.Color.green(),
                    description=f"{new_flip_count}/{MAX_FLIP_RESULTS}"
                )
                embed.add_field(
                    name="Chosen",
                    value=f"`{chosen_display}`",
                    inline=False
                )
                embed.add_field(
                    name="Results",
                    value=f"`{result_display}`",
                    inline=False
                )
                
                if new_flip_count == MAX_FLIP_RESULTS:
                    embed.add_field(
                        name="Status",
                        value="✅ Collection complete! Making first prediction...",
                        inline=False
                    )
                else:
                    embed.set_footer(text=f"Need {MAX_FLIP_RESULTS - new_flip_count} more flips")
                
                await message.channel.send(embed=embed)
                
                # After 25 flips, make the first prediction
                if new_flip_count == MAX_FLIP_RESULTS:
                    analysis = analyze_coin_flip_probability()
                    outcome_pred, outcome_conf = predict_next_outcome()
                    prediction_embed = discord.Embed(
                        title="🔮 First Prediction Made",
                        color=discord.Color.blue(),
                        description=f"Based on last {analysis['total']} flips"
                    )
                    prediction_embed.add_field(
                        name="Win Rate Analysis",
                        value=f"**Heads**: {analysis['heads_wins']}/{analysis['heads_total']} wins ({analysis['heads_win_rate']:.1f}%)\n"
                              f"**Tails**: {analysis['tails_wins']}/{analysis['tails_total']} wins ({analysis['tails_win_rate']:.1f}%)",
                        inline=False
                    )
                    prediction_embed.add_field(
                        name="Win-Rate Prediction",
                        value=f"**{analysis['predicted'].upper()}** (Higher win rate)\nConfidence: {analysis['confidence']:.1f}%",
                        inline=False
                    )
                    prediction_embed.add_field(
                        name="🎯 Outcome Prediction",
                        value=f"**{outcome_pred}**\nConfidence: {outcome_conf}%",
                        inline=False
                    )
                    await message.channel.send(embed=prediction_embed)
                    add_prediction(26, analysis['predicted'])
            
            # After 25 flips - check prediction and make new one
            elif new_flip_count > MAX_FLIP_RESULTS:
                # Get last prediction to check if it was correct
                last_pred = get_last_prediction()
                
                if last_pred:
                    pred_id, flip_num, predicted = last_pred
                    # Use the actual result (what the user chose) for checking prediction
                    is_correct = update_prediction(pred_id, chosen)
                    
                    # Show result of previous prediction
                    result_text = "✅ CORRECT!" if is_correct else "❌ WRONG!"
                    result_color = discord.Color.green() if is_correct else discord.Color.red()
                    
                    result_embed = discord.Embed(
                        title=f"Prediction Result: {result_text}",
                        color=result_color,
                    )
                    result_embed.add_field(
                        name="Details",
                        value=f"Predicted: **{predicted.upper()}**\nActual Chosen: **{chosen.upper()}**\nResult: **{result.upper()}**",
                        inline=False
                    )
                    
                    correct, total = get_prediction_accuracy()
                    accuracy = (correct / total) * 100
                    result_embed.add_field(
                        name="Overall Accuracy",
                        value=f"{correct}/{total} correct ({accuracy:.1f}%)",
                        inline=False
                    )
                    
                    await message.channel.send(embed=result_embed)
                    
                    # Make new prediction with updated data
                    analysis = analyze_coin_flip_probability()
                    outcome_pred, outcome_conf = predict_next_outcome()
                    
                    new_pred_embed = discord.Embed(
                        title="🔮 New Prediction Made",
                        color=discord.Color.blue(),
                    )
                    new_pred_embed.add_field(
                        name="Updated Statistics",
                        value=f"Heads: {analysis['heads_wins']}/{analysis['heads_total']} wins ({analysis['heads_win_rate']:.1f}%)\n"
                              f"Tails: {analysis['tails_wins']}/{analysis['tails_total']} wins ({analysis['tails_win_rate']:.1f}%)",
                        inline=False
                    )
                    new_pred_embed.add_field(
                        name="Win-Rate Prediction",
                        value=f"**{analysis['predicted'].upper()}**\nConfidence: {analysis['confidence']:.1f}%",
                        inline=False
                    )
                    new_pred_embed.add_field(
                        name="🎯 Outcome Prediction",
                        value=f"**{outcome_pred}**\nConfidence: {outcome_conf}%",
                        inline=False
                    )
                    
                    await message.channel.send(embed=new_pred_embed)
                    add_prediction(new_flip_count + 1, analysis['predicted'])
        
        # If only chosen but no result yet, store for potential edit tracking
        elif chosen:
            owo_message_tracking[message.id] = chosen
            print(f"[CF TRACKING] Message {message.id} tracked as: {chosen}")

    await bot.process_commands(message)


@bot.event
async def on_message_edit(before, after):
    """Listen for OWO bot message edits to capture won/lost result."""
    global cf_listening, cf_channel_id, owo_message_tracking
    
    # Auto-start system if OWO coin flip result detected and not already listening
    if after.author.id == OWO_BOT_ID and not cf_listening:
        msg_lower = after.content.lower()
        if "and you won" in msg_lower or "lost it all" in msg_lower or "and you lost" in msg_lower:
            cf_listening = True
            cf_channel_id = after.channel.id
            clear_all_data()
            print(f"[CF AUTO-START FROM EDIT] System started in channel {after.channel.id}")
    
    if not cf_listening or after.author.id != OWO_BOT_ID or after.channel.id != cf_channel_id:
        return
    
    # Check if this message ID was tracked (has chosen value)
    if after.id not in owo_message_tracking:
        return
    
    chosen = owo_message_tracking[after.id]
    msg_lower = after.content.lower()
    result = None
    
    print(f"[OWO EDIT] Message {after.id} edited. New content: {after.content[:100]}")
    
    # Check for won/lost in edited message - be specific to avoid emoji matching
    if "and you lost" in msg_lower or "lost it all" in msg_lower:
        result = "lost"
        print(f"[CF RESULT FROM EDIT] Detected LOST")
    elif "and you won" in msg_lower:
        result = "won"
        print(f"[CF RESULT FROM EDIT] Detected WON")
    
    if result:
        # Remove from tracking
        del owo_message_tracking[after.id]
        
        # Save to database
        flip_count = get_flip_count()
        add_flip_to_db(chosen, result)
        new_flip_count = get_flip_count()
        
        print(f"[CF SAVED] Flip {new_flip_count}/{MAX_FLIP_RESULTS} - {chosen} + {result}")
        
        # First 20 flips - just collect data
        if new_flip_count <= MAX_FLIP_RESULTS:
            flips = get_last_25_flips()
            chosen_display = " ".join([f"{'H' if flip[0] == 'heads' else 'T'}" for flip in flips])
            result_display = " ".join([f"{'W' if flip[1] == 'won' else 'L'}" for flip in flips])
            
            embed = discord.Embed(
                title="✅ Data Saved",
                color=discord.Color.green(),
                description=f"{new_flip_count}/{MAX_FLIP_RESULTS}"
            )
            embed.add_field(
                name="Chosen",
                value=f"`{chosen_display}`",
                inline=False
            )
            embed.add_field(
                name="Results",
                value=f"`{result_display}`",
                inline=False
            )
            
            if new_flip_count == MAX_FLIP_RESULTS:
                embed.add_field(
                    name="Status",
                    value="✅ Collection complete! Making first prediction...",
                    inline=False
                )
            else:
                embed.set_footer(text=f"Need {MAX_FLIP_RESULTS - new_flip_count} more flips")
            
            await after.channel.send(embed=embed)
            
            # After 20 flips, make the first prediction
            if new_flip_count == MAX_FLIP_RESULTS:
                analysis = analyze_coin_flip_probability()
                outcome_pred, outcome_conf = predict_next_outcome()
                prediction_embed = discord.Embed(
                    title="🔮 First Prediction Made",
                    color=discord.Color.blue(),
                    description=f"Based on analysis of {analysis['total']} flips"
                )
                prediction_embed.add_field(
                    name="Win Rate Analysis",
                    value=f"**Heads**: {analysis['heads_wins']}/{analysis['heads_total']} wins ({analysis['heads_win_rate']:.1f}%)\n"
                          f"**Tails**: {analysis['tails_wins']}/{analysis['tails_total']} wins ({analysis['tails_win_rate']:.1f}%)",
                    inline=False
                )
                prediction_embed.add_field(
                    name="Win-Rate Prediction",
                    value=f"**{analysis['predicted'].upper()}** (Higher win rate)\nConfidence: {analysis['confidence']:.1f}%",
                    inline=False
                )
                prediction_embed.add_field(
                    name="🎯 Outcome Prediction",
                    value=f"**{outcome_pred}**\nConfidence: {outcome_conf}%",
                    inline=False
                )
                await after.channel.send(embed=prediction_embed)
                add_prediction(21, analysis['predicted'])
        
        # After 20 flips - check prediction and make new one
        elif new_flip_count > MAX_FLIP_RESULTS:
            last_pred = get_last_prediction()
            
            if last_pred:
                pred_id, flip_num, predicted = last_pred
                is_correct = update_prediction(pred_id, chosen)
                
                result_text = "✅ CORRECT!" if is_correct else "❌ WRONG!"
                result_color = discord.Color.green() if is_correct else discord.Color.red()
                
                result_embed = discord.Embed(
                    title=f"Prediction Result: {result_text}",
                    color=result_color,
                )
                result_embed.add_field(
                    name="Details",
                    value=f"Predicted: **{predicted.upper()}**\nActual Chosen: **{chosen.upper()}**\nResult: **{result.upper()}**",
                    inline=False
                )
                
                correct, total = get_prediction_accuracy()
                accuracy = (correct / total) * 100
                result_embed.add_field(
                    name="Overall Accuracy",
                    value=f"{correct}/{total} correct ({accuracy:.1f}%)",
                    inline=False
                )
                
                await after.channel.send(embed=result_embed)
                
                analysis = analyze_coin_flip_probability()
                outcome_pred, outcome_conf = predict_next_outcome()
                
                new_pred_embed = discord.Embed(
                    title="🔮 New Prediction Made",
                    color=discord.Color.blue(),
                )
                new_pred_embed.add_field(
                    name="Updated Win Rate Analysis",
                    value=f"**Heads**: {analysis['heads_wins']}/{analysis['heads_total']} wins ({analysis['heads_win_rate']:.1f}%)\n"
                          f"**Tails**: {analysis['tails_wins']}/{analysis['tails_total']} wins ({analysis['tails_win_rate']:.1f}%)",
                    inline=False
                )
                new_pred_embed.add_field(
                    name="Win-Rate Prediction",
                    value=f"**{analysis['predicted'].upper()}** (Higher win rate)\nConfidence: {analysis['confidence']:.1f}%",
                    inline=False
                )
                new_pred_embed.add_field(
                    name="🎯 Outcome Prediction",
                    value=f"**{outcome_pred}**\nConfidence: {outcome_conf}%",
                    inline=False
                )
                
                await after.channel.send(embed=new_pred_embed)
                add_prediction(new_flip_count + 1, analysis['predicted'])


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set. Add it to .env before starting the bot.")

bot.run(token)
