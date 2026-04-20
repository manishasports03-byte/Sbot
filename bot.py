import discord
from discord.ext import commands
from datetime import datetime, timezone
from dataclasses import dataclass, field
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
import random
import os
import asyncio
import yt_dlp
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
    "admin bulaun kya \U0001f440"
]

afk_users = {}
MAX_AFK_PINGS_TO_SHOW = 5
MAX_SPOTIFY_PLAYLIST_TRACKS = 50
music_loop_enabled = {}


@dataclass
class MusicState:
    queue: list = field(default_factory=list)
    current: dict | None = None
    volume: float = 1.0
    loop: bool = False
    text_channel_id: int | None = None
    skip_requested: bool = False


music_states = {}


def get_queue_state(ctx):
    state_key = ctx.guild.id if ctx.guild else ctx.author.id
    state = music_states.get(state_key)

    if state is None:
        state = MusicState()
        music_states[state_key] = state

    return state


def get_queue_state_for_guild(guild):
    if not guild:
        return None

    state = music_states.get(guild.id)

    if state is None:
        state = MusicState()
        music_states[guild.id] = state

    return state


def format_music_duration(seconds):
    total_seconds = int(seconds or 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    return f"{minutes}:{seconds:02d}"


def format_music_track(track):
    url = track.get("webpage_url")
    title = track.get("title", "Unknown track")
    return f"[{title}]({url})" if url else title


def build_ytdlp_now_playing_embed(track):
    embed = discord.Embed(title="\U0001f4bf Now Playing", color=discord.Color.dark_gray())
    embed.description = (
        f"{format_music_track(track)}\n"
        f"By: `{track.get('uploader', 'Unknown')}`\n"
        f"Duration: `{format_music_duration(track.get('duration'))}`\n"
        f"Requested by _{track.get('requester', 'Unknown')}_"
    )

    if track.get("thumbnail"):
        embed.set_thumbnail(url=track["thumbnail"])

    return embed


def build_ytdlp_queue_embed(state, page):
    tracks = state.queue
    per_page = 10
    total_pages = max(1, (len(tracks) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    page_tracks = tracks[start:start + per_page]

    embed = discord.Embed(title="Music Queue", color=discord.Color.dark_gray())

    if state.current:
        embed.description = (
            f"Now Playing: {format_music_track(state.current)}\n"
            f"By: `{state.current.get('uploader', 'Unknown')}`\n\n"
        )
    else:
        embed.description = "Nothing is playing right now.\n\n"

    if page_tracks:
        lines = []
        for index, track in enumerate(page_tracks, start=start + 1):
            lines.append(
                f"`{index}` • {track.get('title', 'Unknown track')} — {track.get('uploader', 'Unknown')}"
            )
        embed.description += "\n".join(lines)
    else:
        embed.description += "The queue is currently empty."

    embed.set_footer(text=f"Page {page + 1}/{total_pages}")
    return embed


def build_ytdlp_queued_embed(track, position):
    embed = discord.Embed(title="Track Queued", color=discord.Color.dark_gray())
    embed.description = (
        f"\u2705 {format_music_track(track)} added to queue.\n"
        f"By: `{track.get('uploader', 'Unknown')}`\n"
        f"Position: `{position}`"
    )
    return embed


def _extract_track_data(query):
    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch",
        "extract_flat": False
    }
    cleaned_query = query.strip()
    lookup = cleaned_query if cleaned_query.lower().startswith(("http://", "https://")) else f"ytsearch1:{cleaned_query}"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(lookup, download=False)

    if not info:
        return None

    if "entries" in info:
        entries = info.get("entries") or []
        if not entries:
            return None
        info = entries[0]

    stream_url = info.get("url")

    if not stream_url:
        formats = info.get("formats") or []
        for item in reversed(formats):
            if item.get("url"):
                stream_url = item["url"]
                break

    return {
        "title": info.get("title") or cleaned_query,
        "uploader": info.get("uploader") or info.get("channel") or "Unknown",
        "duration": info.get("duration") or 0,
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or info.get("original_url"),
        "stream_url": stream_url,
        "search_query": cleaned_query
    }


async def fetch_track(query, requester):
    track = await asyncio.to_thread(_extract_track_data, query)
    if not track:
        return None
    track["requester"] = requester
    return track


async def refresh_track(track):
    source = track.get("webpage_url") or track.get("search_query")
    refreshed = await asyncio.to_thread(_extract_track_data, source)

    if not refreshed:
        return None

    refreshed["requester"] = track.get("requester", "Unknown")
    return refreshed


async def connect_music_voice(ctx):
    if ctx.author.voice is None:
        await ctx.send("Join a VC first.")
        return None

    channel = ctx.author.voice.channel

    if ctx.voice_client:
        if ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
        return ctx.voice_client

    return await channel.connect(reconnect=True)


def schedule_music_advance(guild_id, error):
    if error:
        print(f"Playback error in guild {guild_id}: {error}")

    asyncio.run_coroutine_threadsafe(advance_music_queue(guild_id), bot.loop)


async def start_next_track(guild):
    state = get_queue_state_for_guild(guild)
    voice_client = guild.voice_client if guild else None

    if not state or not voice_client or not voice_client.is_connected():
        return

    while state.queue:
        queued_track = state.queue.pop(0)
        playable_track = await refresh_track(queued_track)

        if not playable_track or not playable_track.get("stream_url"):
            continue

        state.current = playable_track

        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    playable_track["stream_url"],
                    before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                    options="-vn"
                ),
                volume=state.volume
            )
            voice_client.play(
                source,
                after=lambda error, guild_id=guild.id: schedule_music_advance(guild_id, error)
            )
        except Exception:
            state.current = None
            continue

        if state.text_channel_id:
            channel = bot.get_channel(state.text_channel_id)
            if channel:
                await channel.send(embed=build_ytdlp_now_playing_embed(playable_track), view=YTDLPNowPlayingView())

        return

    state.current = None


async def advance_music_queue(guild_id):
    guild = bot.get_guild(guild_id)
    state = get_queue_state_for_guild(guild)

    if not guild or not state:
        return

    finished_track = state.current

    if state.skip_requested:
        state.skip_requested = False
    elif finished_track and state.loop:
        state.queue.append(finished_track.copy())

    state.current = None

    voice_client = guild.voice_client
    if voice_client and voice_client.is_connected():
        await start_next_track(guild)


async def queue_music_queries(ctx, queries, source_type="track"):
    state = get_queue_state(ctx)
    voice_client = await connect_music_voice(ctx)

    if not voice_client:
        return

    state.text_channel_id = ctx.channel.id
    queued_tracks = []
    queued_positions = []

    if source_type != "track":
        await ctx.send(f"Loading Spotify {source_type}...")

    for query in queries:
        track = await fetch_track(query, ctx.author.display_name)
        if not track:
            continue
        state.queue.append(track)
        queued_tracks.append(track)
        queued_positions.append(len(state.queue))

    if not queued_tracks:
        if source_type == "track":
            await ctx.send("No songs found.")
        else:
            await ctx.send("\u274c I could not match those Spotify tracks on YouTube.")
        return

    if not voice_client.is_playing() and not voice_client.is_paused() and not state.current:
        await start_next_track(ctx.guild)

    if source_type == "track":
        await ctx.send(embed=build_ytdlp_queued_embed(queued_tracks[0], queued_positions[0]))
    else:
        count = len(queued_tracks)
        await ctx.send(f"Queued {count} track{'s' if count != 1 else ''} from Spotify.")


class YTDLPNowPlayingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    def get_voice_and_state(self, interaction):
        guild = interaction.guild
        if not guild:
            return None, None
        return guild.voice_client, get_queue_state_for_guild(guild)

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction, button):
        voice_client, state = self.get_voice_and_state(interaction)

        if not voice_client or not state or not state.current:
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
            return

        if voice_client.is_paused():
            voice_client.resume()
            button.label = "Pause"
        else:
            voice_client.pause()
            button.label = "Resume"

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction, button):
        voice_client, state = self.get_voice_and_state(interaction)

        if not voice_client or not state or not state.current:
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
            return

        state.skip_requested = True
        voice_client.stop()
        await interaction.response.send_message("Skipped.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction, button):
        voice_client, state = self.get_voice_and_state(interaction)

        if not voice_client or not state:
            await interaction.response.send_message("I am not playing anything.", ephemeral=True)
            return

        state.queue.clear()
        state.current = None
        state.skip_requested = False
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()

        await interaction.response.send_message("Stopped and cleared the queue.", ephemeral=True)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary)
    async def loop_button(self, interaction, button):
        voice_client, state = self.get_voice_and_state(interaction)

        if not interaction.guild or not voice_client or not state:
            await interaction.response.send_message("Loop only works inside a server.", ephemeral=True)
            return

        state.loop = not state.loop
        music_loop_enabled[interaction.guild.id] = state.loop
        await interaction.response.send_message(
            f"Loop {'enabled' if state.loop else 'disabled'}.",
            ephemeral=True
        )

    @discord.ui.button(label="Shuffle", style=discord.ButtonStyle.secondary)
    async def shuffle_button(self, interaction, button):
        voice_client, state = self.get_voice_and_state(interaction)

        if not voice_client or not state or not state.queue:
            await interaction.response.send_message("The queue is currently empty.", ephemeral=True)
            return

        random.shuffle(state.queue)
        await interaction.response.send_message("Queue shuffled.", ephemeral=True)


class YTDLPQueueView(discord.ui.View):
    def __init__(self, guild_id, author_id):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.author_id = author_id
        self.page = 0
        self.update_buttons()

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This queue menu is not for you.", ephemeral=True)
            return False

        return True

    def get_state(self):
        return music_states.get(self.guild_id)

    def update_buttons(self):
        state = self.get_state()
        queue_length = len(state.queue) if state else 0
        total_pages = max(1, (queue_length + 9) // 10)
        self.previous_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= total_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction, button):
        state = self.get_state()

        if not state:
            await interaction.response.send_message("The queue is no longer available.", ephemeral=True)
            return

        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=build_ytdlp_queue_embed(state, self.page), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction, button):
        state = self.get_state()

        if not state:
            await interaction.response.send_message("The queue is no longer available.", ephemeral=True)
            return

        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=build_ytdlp_queue_embed(state, self.page), view=self)


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

    # Bot cannot change the guild owner's nickname due to Discord restrictions
    if member.id != member.guild.owner_id:
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
    
    # Bot cannot change the guild owner's nickname due to Discord restrictions
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
                allowed_mentions=discord.AllowedMentions(roles=False, users=False)
            )
        else:
            await member.add_roles(role, reason=f"Role toggled by {message.author}")
            await message.channel.send(
                f"Added **{role.name}** to **{member.display_name}**.",
                allowed_mentions=discord.AllowedMentions(roles=False, users=False)
            )
    except discord.Forbidden:
        await message.channel.send("Discord blocked that role change. Check role order and permissions.")
    except discord.HTTPException:
        await message.channel.send("Could not change that role right now. Try again later.")


def format_track(track):
    if track.uri:
        return f"[{track.title}]({track.uri})"

    return track.title


def format_track_duration(track):
    total_seconds = int((track.length or 0) / 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def set_track_requester(ctx, track):
    music_requesters[getattr(track, "identifier", track.title)] = ctx.author.display_name


def get_track_requester(track):
    return music_requesters.get(getattr(track, "identifier", track.title), "Unknown")


def build_track_queued_embed(track):
    embed = discord.Embed(title="Track Queued", color=discord.Color.dark_gray())
    embed.description = (
        f"\u2705 {format_track(track)} added to queue. "
        f"Artist: `{track.author}`"
    )
    return embed


def build_now_playing_embed(track):
    embed = discord.Embed(title="\U0001f4bf Now Playing", color=discord.Color.dark_gray())
    embed.description = (
        f"{format_track(track)} - `{track.author}`\n"
        f"Duration: `{format_track_duration(track)}`\n"
        f"Requested by _{get_track_requester(track)}_"
    )

    if track.artwork:
        embed.set_thumbnail(url=track.artwork)

    return embed


def build_queue_embed(player, tracks, page):
    per_page = 10
    total_pages = max(1, (len(tracks) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    page_tracks = tracks[start:start + per_page]

    embed = discord.Embed(title="Now Playing", color=discord.Color.dark_gray())

    if player.current:
        embed.description = (
            f"{player.current.title}\n"
            f"By: {player.current.author}\n\n"
        )
    else:
        embed.description = "Nothing is playing right now.\n\n"

    queue_lines = []
    for index, track in enumerate(page_tracks, start=start + 1):
        queue_lines.append(f"`{index}` • {track.title} — {track.author}")

    embed.description += "\n".join(queue_lines) if queue_lines else "The queue is currently empty."
    embed.set_footer(text=f"Page {page + 1}/{total_pages}")
    return embed


def build_music_action_embed(message, hint=None):
    embed = discord.Embed(color=discord.Color.dark_gray())
    embed.description = f"\u2705 {message}"

    if hint:
        embed.description += f"\n\n{hint}"

    return embed


async def send_notice(ctx, message):
    embed = discord.Embed(description=message, color=discord.Color.dark_gray())
    await ctx.send(embed=embed)


async def send_success(ctx, message):
    embed = discord.Embed(description=f"\u2705 {message}", color=discord.Color.dark_gray())
    await ctx.send(embed=embed)


async def send_bot_info(ctx):
    guild_id = ctx.guild.id if ctx.guild else "DM"
    embed = discord.Embed(title=f"{bot.user.display_name} Music", color=discord.Color.dark_gray())
    embed.description = (
        "Hey I'm a best quality music bot!\n\n"
        "**Guild Settings**\n"
        "Prefix : `none`\n"
        "Language : Eng\n"
        f"Server Id : `{guild_id}`\n\n"
        "Made with \u2764 by @_anuneet1x"
    )

    if bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    await ctx.send(embed=embed, view=BotInfoView())


def is_spotify_url(query):
    lowered = query.lower()
    return "open.spotify.com/" in lowered or lowered.startswith("spotify:")


def is_spotify_premium_required_error(error):
    message = str(error).lower()
    return (
        getattr(error, "http_status", None) == 403
        and "premium subscription required" in message
    )


def get_spotify_client():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        return None

    auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    return spotipy.Spotify(auth_manager=auth)


def spotify_track_to_search(track):
    artists = ", ".join(artist["name"] for artist in track.get("artists", []))
    return f"{track['name']} {artists}".strip()


def resolve_spotify_url(query):
    spotify = get_spotify_client()

    if not spotify:
        raise RuntimeError("Spotify API credentials are missing.")

    lowered = query.lower()
    clean_query = query.split("?")[0]

    if "/track/" in lowered or lowered.startswith("spotify:track:"):
        track = spotify.track(clean_query)
        return "track", [spotify_track_to_search(track)]

    if "/album/" in lowered or lowered.startswith("spotify:album:"):
        album = spotify.album(clean_query)
        searches = [
            spotify_track_to_search(track)
            for track in album["tracks"]["items"][:MAX_SPOTIFY_PLAYLIST_TRACKS]
        ]
        return "album", searches

    if "/playlist/" in lowered or lowered.startswith("spotify:playlist:"):
        searches = []
        results = spotify.playlist_items(
            clean_query,
            additional_types=("track",),
            limit=100
        )

        while results and len(searches) < MAX_SPOTIFY_PLAYLIST_TRACKS:
            for item in results["items"]:
                track = item.get("track")
                if not track or track.get("is_local"):
                    continue

                searches.append(spotify_track_to_search(track))

                if len(searches) >= MAX_SPOTIFY_PLAYLIST_TRACKS:
                    break

            results = spotify.next(results) if results.get("next") else None

        return "playlist", searches

    raise RuntimeError("That Spotify link type is not supported yet.")


async def resolve_spotify_url_async(query):
    return await bot.loop.run_in_executor(None, resolve_spotify_url, query)


def strip_search_prefix(query):
    query = query.strip()
    prefixes = ("ytsearch:", "ytmsearch:", "scsearch:", "amsearch:", "spsearch:")
    lowered = query.lower()

    for prefix in prefixes:
        if lowered.startswith(prefix):
            return query[len(prefix):].strip()

    return query


def _extract_stream_url(query):
    ydl_opts = {
        "format": "bestaudio",
        "noplaylist": True,
        "quiet": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)
        entries = info.get("entries") or []

        if not entries:
            return None

        return entries[0].get("url")


async def get_stream_url(query):
    return await asyncio.to_thread(_extract_stream_url, query)


def build_music_search_query(query):
    query = strip_search_prefix(query)
    lowered = query.lower()
    search_prefixes = ("scsearch:", "ytsearch:", "ytmsearch:", "amsearch:", "spsearch:")

    if lowered.startswith(search_prefixes) or lowered.startswith(("http://", "https://")):
        return query

    return f"ytsearch:{query}"


def official_track_score(track):
    title = track.title.lower()
    author = (track.author or "").lower()
    combined = f"{title} {author}"
    score = 0

    official_signals = (
        "official",
        "provided to youtube",
        "topic",
        "vevo",
        "records",
        "music",
        "audio"
    )
    bad_signals = (
        "cover",
        "remix",
        "slowed",
        "reverb",
        "nightcore",
        "karaoke",
        "instrumental",
        "lyrics",
        "lyric",
        "live",
        "sped up",
        "8d",
        "lofi"
    )

    for signal in official_signals:
        if signal in combined:
            score += 4

    for signal in bad_signals:
        if signal in combined:
            score -= 5

    if "official music video" in title or "official audio" in title:
        score += 8

    if "topic" in author:
        score += 6

    return score


def pick_best_track(tracks):
    return max(tracks, key=official_track_score)


async def connect_lavalink():
    global lavalink_connected

    if lavalink_connected:
        return

    node = wavelink.Node(
        uri="ws://13.127.61.86:2333",
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


def get_voice_client(ctx):
    voice_client = ctx.voice_client

    if isinstance(voice_client, discord.VoiceClient):
        return voice_client

    return None


def get_music_state_key(ctx):
    if ctx.guild:
        return ctx.guild.id

    return ctx.author.id


async def get_or_connect_player(ctx):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await send_notice(ctx, "Join a voice channel first.")
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


async def search_best_track(query):
    clean_query = strip_search_prefix(query)
    search_query = build_music_search_query(clean_query)
    tracks = await wavelink.Playable.search(search_query)

    if not tracks:
        print("YT failed, trying SoundCloud...")
        tracks = await wavelink.Playable.search(f"scsearch:{clean_query}")

    print(f"Tracks found: {len(tracks)}")

    if not tracks or isinstance(tracks, wavelink.Playlist):
        return None

    for index, found_track in enumerate(tracks[:5], start=1):
        print(
            f"Result {index}: {found_track.title} - {found_track.author} "
            f"(score {official_track_score(found_track)})"
        )

    return pick_best_track(tracks)


async def queue_spotify_tracks(ctx, player, searches, source_type):
    if not searches:
        await ctx.send("\u274c No Spotify tracks found.")
        return

    queued = 0
    first_track = None

    await ctx.send(f"Loading Spotify {source_type}...")

    for search in searches:
        try:
            track = await search_best_track(search)
        except wavelink.LavalinkLoadException:
            continue

        if not track:
            continue

        set_track_requester(ctx, track)

        if not first_track and not player.playing and not player.paused:
            first_track = track
        else:
            player.queue.put(track)
            queued += 1

    if first_track:
        await player.play(first_track)
        await ctx.send(embed=build_now_playing_embed(first_track), view=NowPlayingView())

    if queued:
        await ctx.send(f"Queued {queued} track{'s' if queued != 1 else ''} from Spotify.")

    if not first_track and not queued:
        await ctx.send("\u274c I could not match those Spotify tracks on YouTube Music.")


class NowPlayingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    def get_player(self, interaction):
        player = interaction.guild.voice_client if interaction.guild else None

        if not isinstance(player, wavelink.Player):
            return None

        return player

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction, button):
        player = self.get_player(interaction)

        if not player or not player.current:
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
            return

        await player.pause(not player.paused)
        button.label = "Resume" if player.paused else "Pause"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction, button):
        player = self.get_player(interaction)

        if not player or not player.current:
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
            return

        await player.skip(force=True)
        await interaction.response.send_message("Skipped.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction, button):
        player = self.get_player(interaction)

        if not player:
            await interaction.response.send_message("I am not playing anything.", ephemeral=True)
            return

        player.queue.clear()
        await player.stop()
        await interaction.response.send_message("Stopped and cleared the queue.", ephemeral=True)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary)
    async def loop_button(self, interaction, button):
        if not interaction.guild:
            await interaction.response.send_message("Loop only works inside a server.", ephemeral=True)
            return

        guild_id = interaction.guild.id
        music_loop_enabled[guild_id] = not music_loop_enabled.get(guild_id, False)
        state = "enabled" if music_loop_enabled[guild_id] else "disabled"
        await interaction.response.send_message(f"Loop {state}.", ephemeral=True)

    @discord.ui.button(label="Shuffle", style=discord.ButtonStyle.secondary)
    async def shuffle_button(self, interaction, button):
        player = self.get_player(interaction)

        if not player or player.queue.is_empty:
            await interaction.response.send_message("The queue is currently empty.", ephemeral=True)
            return

        player.queue.shuffle()
        await interaction.response.send_message("Queue shuffled.", ephemeral=True)


class QueueView(discord.ui.View):
    def __init__(self, player, tracks, author_id):
        super().__init__(timeout=180)
        self.player = player
        self.tracks = tracks
        self.author_id = author_id
        self.page = 0
        self.update_buttons()

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This queue menu is not for you.",
                ephemeral=True
            )
            return False

        return True

    def update_buttons(self):
        total_pages = max(1, (len(self.tracks) + 9) // 10)
        self.previous_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= total_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction, button):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(
            embed=build_queue_embed(self.player, self.tracks, self.page),
            view=self
        )

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction, button):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(
            embed=build_queue_embed(self.player, self.tracks, self.page),
            view=self
        )


class BotInfoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        permissions = discord.Permissions(
            send_messages=True,
            embed_links=True,
            connect=True,
            speak=True,
            manage_nicknames=True,
            manage_roles=True
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
            discord.SelectOption(label="Filters", emoji="🎚️"),
            discord.SelectOption(label="Info", emoji="ℹ️"),
            discord.SelectOption(label="Music", emoji="🎵"),
            discord.SelectOption(label="Owner", emoji="👑"),
            discord.SelectOption(label="Playlist", emoji="📋"),
            discord.SelectOption(label="Premium", emoji="💎"),
            discord.SelectOption(label="Purge", emoji="➕"),
            discord.SelectOption(label="Server", emoji="🖥️"),
            discord.SelectOption(label="Spotify", emoji="🎧"),
        ]
        
        self.add_item(discord.ui.Select(
            placeholder="Select Main Category",
            options=categories,
            custom_id="lunexa_category"
        ))
    
    async def interaction_check(self, interaction):
        if interaction.data.get("custom_id") == "lunexa_category":
            category = interaction.data.get("values")[0]
            await interaction.response.defer()
            await interaction.followup.send(f"You selected: **{category}**", ephemeral=True)
        return True


async def send_lunexa_welcome(ctx):
    guild_id = ctx.guild.id if ctx.guild else "DM"
    embed = discord.Embed(
        title="poyoyoi Music",
        color=discord.Color.dark_gray()
    )
    embed.description = (
        "Hey I'm a best quality music bot!\n\n"
        "**Guild Settings**\n"
        "Prefix : `none`\n"
        "Language : Eng\n"
        f"Server Id : `{guild_id}`\n\n"
        "Made with ❤ by @_anuneet1x"
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
                ephemeral=True
            )
            return False

        return True

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm_afk(self, interaction, button):
        # Check if the member is the guild owner
        if self.member.id == self.member.guild.owner_id:
            await interaction.response.edit_message(
                content=f"{self.member.mention} you are the server owner, you can't set AFK!",
                view=None
            )
            return

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


@bot.command(name="join")
async def join_command(ctx):
    voice_client = await connect_music_voice(ctx)

    if voice_client:
        await send_success(ctx, f"Joined **{voice_client.channel.name}** successfully.")


@bot.command(name="about", aliases=["info"])
async def about_command(ctx):
    await send_bot_info(ctx)


@bot.command(name="play", aliases=["p"])
async def play_command(ctx, *, query=None):
    if not query:
        await ctx.send("Use it like: `play song name or link`")
        return

    if is_spotify_url(query):
        try:
            source_type, searches = await resolve_spotify_url_async(query)
        except RuntimeError as error:
            await ctx.send(str(error))
            return
        except Exception:
            await ctx.send("Could not read that Spotify link right now.")
            return

        await queue_music_queries(ctx, searches, source_type)
        return

    await queue_music_queries(ctx, [strip_search_prefix(query)])


@bot.command(name="pause")
async def pause_command(ctx):
    voice_client = ctx.voice_client
    state = get_queue_state(ctx)

    if not voice_client or not state.current or not voice_client.is_playing():
        await ctx.send("Nothing is playing right now.")
        return

    voice_client.pause()
    await ctx.send(
        embed=build_music_action_embed(
            "Music has been successfully paused.",
            "Use `resume` to play it again."
        )
    )


@bot.command(name="resume")
async def resume_command(ctx):
    voice_client = ctx.voice_client
    state = get_queue_state(ctx)

    if not voice_client or not state.current or not voice_client.is_paused():
        await ctx.send("Nothing is playing right now.")
        return

    voice_client.resume()
    await ctx.send(
        embed=build_music_action_embed(
            "Music playback has been resumed.",
            "Enjoy your music!"
        )
    )


@bot.command(name="skip", aliases=["s"])
async def skip_command(ctx):
    voice_client = ctx.voice_client
    state = get_queue_state(ctx)

    if not voice_client or not state.current or not (voice_client.is_playing() or voice_client.is_paused()):
        await ctx.send("Nothing is playing right now.")
        return

    state.skip_requested = True
    voice_client.stop()
    await ctx.send(
        embed=build_music_action_embed(
            "Skipped the current song.",
            "Playing the next track."
        )
    )


@bot.command(name="stop")
async def stop_command(ctx):
    voice_client = ctx.voice_client
    state = get_queue_state(ctx)

    if not voice_client:
        await ctx.send("I am not playing anything.")
        return

    state.queue.clear()
    state.current = None
    state.skip_requested = False
    state.loop = False
    music_loop_enabled[get_music_state_key(ctx)] = False

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    await ctx.send("Stopped and cleared the queue.")


@bot.command(name="leave", aliases=["disconnect", "dc"])
async def leave_command(ctx):
    voice_client = ctx.voice_client
    if not voice_client:
        await ctx.send("I am not connected to voice.")
        return

    state = get_queue_state(ctx)
    state.queue.clear()
    state.current = None
    state.skip_requested = False
    state.loop = False
    music_loop_enabled[get_music_state_key(ctx)] = False

    await voice_client.disconnect()
    await ctx.send(embed=build_music_action_embed("Bot has been disconnected from the voice channel."))


@bot.command(name="nowplaying", aliases=["np"])
async def nowplaying_command(ctx):
    voice_client = ctx.voice_client
    state = get_queue_state(ctx)

    if not voice_client or not state.current or not (voice_client.is_playing() or voice_client.is_paused()):
        await ctx.send("Nothing is playing right now.")
        return

    await ctx.send(embed=build_ytdlp_now_playing_embed(state.current), view=YTDLPNowPlayingView())


@bot.command(name="queue", aliases=["q"])
async def queue_command(ctx):
    state = get_queue_state(ctx)

    if not state.current and not state.queue:
        await send_notice(ctx, "The queue is currently empty.")
        return

    await ctx.send(
        embed=build_ytdlp_queue_embed(state, 0),
        view=YTDLPQueueView(ctx.guild.id, ctx.author.id)
    )


@bot.command(name="volume", aliases=["vol"])
async def volume_command(ctx, volume: int = None):
    voice_client = ctx.voice_client
    state = get_queue_state(ctx)

    if not voice_client:
        await ctx.send("I am not connected to voice.")
        return

    if volume is None:
        current_volume = int(state.volume * 100)
        await ctx.send(f"Current volume: {current_volume}%")
        return

    volume = max(0, min(volume, 100))
    state.volume = volume / 100

    if voice_client.source and hasattr(voice_client.source, "volume"):
        voice_client.source.volume = state.volume

    await ctx.send(f"Volume set to {volume}%.")


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

