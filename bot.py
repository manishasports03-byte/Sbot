import discord
from discord.ext import commands
from datetime import datetime, timezone
import wavelink
import random
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

bad_words = ["mc", "bc", "madarchod", "bhosdike", "chutiya", "idiot", "stupid"]

responses = [
    "bhai chill kar \U0001f602",
    "itna gussa kyu \U0001f62d",
    "language control bro \U0001f624",
    "cool banne ki koshish fail \U0001f480",
    "admin bulaun kya \U0001f440"
]

afk_users = {}
MAX_AFK_PINGS_TO_SHOW = 5
lavalink_connected = False


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

    await member.edit(nick=afk_name[:32], reason="User set AFK")
    afk_users[member.id] = {
        "nick": original_nick,
        "since": datetime.now(timezone.utc),
        "pings": [],
        "reason": reason
    }


async def remove_afk(member):
    if member.id not in afk_users:
        return None

    afk_data = afk_users.pop(member.id)
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
            await message.channel.send(f"Removed {role.mention} from {member.mention}.")
        else:
            await member.add_roles(role, reason=f"Role toggled by {message.author}")
            await message.channel.send(f"Added {role.mention} to {member.mention}.")
    except discord.Forbidden:
        await message.channel.send("Discord blocked that role change. Check role order and permissions.")
    except discord.HTTPException:
        await message.channel.send("Could not change that role right now. Try again later.")


def format_track(track):
    if track.uri:
        return f"[{track.title}]({track.uri})"

    return track.title


async def connect_lavalink():
    global lavalink_connected

    if lavalink_connected:
        return

    node = wavelink.Node(
        identifier="main",
        uri="wss://lavalink-4-production-d73d.up.railway.app",
        password="youshallnotpass"
    )
    await wavelink.Pool.connect(nodes=[node], client=bot)
    lavalink_connected = True


def get_player(ctx):
    player = ctx.voice_client

    if not player:
        return None

    if not isinstance(player, wavelink.Player):
        return None

    return player


async def get_or_connect_player(ctx):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("Join a voice channel first.")
        return None

    player = get_player(ctx)
    channel = ctx.author.voice.channel

    if player:
        if player.channel != channel:
            await player.move_to(channel)
        return player

    try:
        return await channel.connect(cls=wavelink.Player, self_deaf=True)
    except wavelink.InvalidNodeException:
        await ctx.send("Lavalink is not connected yet. Check Railway logs and Lavalink env vars.")
    except discord.ClientException:
        await ctx.send("I am already connected to a voice channel.")
    except discord.Forbidden:
        await ctx.send("I need permission to join/speak in your voice channel.")
    except discord.HTTPException:
        await ctx.send("Could not join the voice channel right now.")

    return None


async def play_next(player):
    if not player or player.queue.is_empty:
        return

    try:
        next_track = player.queue.get()
    except wavelink.QueueEmpty:
        return

    await player.play(next_track)


class AFKConfirmView(discord.ui.View):
    def __init__(self, member, reason=None):
        super().__init__(timeout=30)
        self.member = member
        self.reason = reason

    async def interaction_check(self, interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "ye button tumhare liye nahi hai bro",
                ephemeral=True
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
                view=None
            )
            return
        except discord.HTTPException:
            await interaction.response.edit_message(
                content="Could not change your nickname right now. Try again later.",
                view=None
            )
            return

        await interaction.response.edit_message(
            content=f"{self.member.mention} is now AFK.{format_afk_reason(self.reason)}",
            view=None
        )

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def cancel_afk(self, interaction, button):
        await interaction.response.edit_message(
            content="AFK cancelled.",
            view=None
        )


@bot.event
async def on_ready():
    try:
        await connect_lavalink()
        print("Lavalink node connected.")
    except Exception as exc:
        print(f"Lavalink connection failed: {exc}")

    print(f"\u2705 Bot is online as {bot.user}")


@bot.event
async def on_wavelink_track_end(payload):
    await play_next(payload.player)


@bot.command(name="join")
async def join_command(ctx):
    player = await get_or_connect_player(ctx)

    if player:
        await ctx.send(f"Joined {player.channel.mention}.")


@bot.command(name="play", aliases=["p"])
async def play_command(ctx, *, query=None):
    if not query:
        await ctx.send("Use it like: `!play song name or link`")
        return

    player = await get_or_connect_player(ctx)
    if not player:
        return

    search_query = query if query.lower().startswith("scsearch:") else f"scsearch:{query}"

    try:
        tracks = await wavelink.Playable.search(search_query)
    except wavelink.LavalinkLoadException:
        await ctx.send("Lavalink could not load that track.")
        return
    except wavelink.InvalidNodeException:
        await ctx.send("Lavalink is not connected yet.")
        return

    print(f"Tracks found: {len(tracks)}")

    if not tracks:
        await ctx.send("\u274c No songs found.")
        return

    if isinstance(tracks, wavelink.Playlist):
        added = player.queue.put(tracks)
        await ctx.send(f"Queued playlist `{tracks.name}` with {added} tracks.")
    else:
        track = tracks[0]
        player.queue.put(track)
        await ctx.send(f"Queued {format_track(track)}.")

    if not player.playing:
        await play_next(player)
        if player.current:
            await ctx.send(f"\U0001f3b6 Playing: {player.current.title}")


@bot.command(name="pause")
async def pause_command(ctx):
    player = get_player(ctx)

    if not player or not player.playing:
        await ctx.send("Nothing is playing right now.")
        return

    await player.pause(True)
    await ctx.send("Paused.")


@bot.command(name="resume")
async def resume_command(ctx):
    player = get_player(ctx)

    if not player:
        await ctx.send("Nothing is playing right now.")
        return

    await player.pause(False)
    await ctx.send("Resumed.")


@bot.command(name="skip", aliases=["s"])
async def skip_command(ctx):
    player = get_player(ctx)

    if not player or not player.playing:
        await ctx.send("Nothing is playing right now.")
        return

    await player.skip(force=True)
    await ctx.send("Skipped.")


@bot.command(name="stop")
async def stop_command(ctx):
    player = get_player(ctx)

    if not player:
        await ctx.send("I am not playing anything.")
        return

    player.queue.clear()
    await player.stop()
    await ctx.send("Stopped and cleared the queue.")


@bot.command(name="leave", aliases=["disconnect", "dc"])
async def leave_command(ctx):
    player = get_player(ctx)

    if not player:
        await ctx.send("I am not connected to voice.")
        return

    await player.disconnect()
    await ctx.send("Left the voice channel.")


@bot.command(name="nowplaying", aliases=["np"])
async def nowplaying_command(ctx):
    player = get_player(ctx)

    if not player or not player.current:
        await ctx.send("Nothing is playing right now.")
        return

    await ctx.send(f"Now playing: {format_track(player.current)}")


@bot.command(name="queue", aliases=["q"])
async def queue_command(ctx):
    player = get_player(ctx)

    if not player:
        await ctx.send("I am not playing anything.")
        return

    if player.queue.is_empty:
        await ctx.send("Queue is empty.")
        return

    tracks = list(player.queue)[:10]
    lines = [f"{index}. {track.title}" for index, track in enumerate(tracks, start=1)]
    remaining = len(player.queue) - len(tracks)

    if remaining:
        lines.append(f"And {remaining} more.")

    await ctx.send("Queue:\n" + "\n".join(lines))


@bot.command(name="volume", aliases=["vol"])
async def volume_command(ctx, volume: int = None):
    player = get_player(ctx)

    if not player:
        await ctx.send("I am not connected to voice.")
        return

    if volume is None:
        await ctx.send(f"Current volume: {player.volume}%")
        return

    volume = max(0, min(volume, 100))
    await player.set_volume(volume)
    await ctx.send(f"Volume set to {volume}%.")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content.lower()

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
            view=AFKConfirmView(message.author, afk_reason)
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
            afk_data["pings"].append({
                "by": message.author.display_name,
                "url": message.jump_url,
                "time": datetime.now(timezone.utc)
            })
            await message.channel.send(
                f"{mentioned_user.mention} is AFK right now. AFK for {afk_duration}."
                f"{reason_text}"
            )
            continue

    await bot.process_commands(message)


token = os.getenv('DISCORD_TOKEN')
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set. Add it to .env before starting the bot.")

bot.run(token)
