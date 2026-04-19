import discord
from discord.ext import commands
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

mention_responses = {
    1476689941252800676: "so rhi hu",
    760729575789166652: "lmao ded \U0001f938\u200d\u2642\ufe0f"
}

afk_users = {}


async def set_afk(member):
    original_nick = member.nick
    display_name = member.display_name

    if display_name.startswith("[AFK] "):
        afk_name = display_name
    else:
        afk_name = f"[AFK] {display_name}"

    afk_users[member.id] = original_nick
    await member.edit(nick=afk_name[:32], reason="User set AFK")


async def remove_afk(member):
    if member.id not in afk_users:
        return False

    original_nick = afk_users.pop(member.id)
    await member.edit(nick=original_nick, reason="User returned from AFK")
    return True


class AFKConfirmView(discord.ui.View):
    def __init__(self, member):
        super().__init__(timeout=30)
        self.member = member

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
            await set_afk(self.member)
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
            content=f"{self.member.mention} is now AFK.",
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
    print(f"\u2705 Bot is online as {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content.lower()

    if msg == "afk":
        if not message.guild:
            await message.channel.send("AFK nickname changes only work inside a server.")
            return

        await message.channel.send(
            f"{message.author.mention} are you going AFK?",
            view=AFKConfirmView(message.author)
        )
        return

    if message.guild and message.author.id in afk_users:
        try:
            await remove_afk(message.author)
            await message.channel.send(f"Welcome back {message.author.mention}, AFK removed.")
        except discord.Forbidden:
            afk_users.pop(message.author.id, None)
            await message.channel.send(
                f"Welcome back {message.author.mention}. I could not restore your nickname."
            )
        except discord.HTTPException:
            await message.channel.send(
                f"Welcome back {message.author.mention}. I could not restore your nickname right now."
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
            await message.channel.send(f"{mentioned_user.mention} is AFK right now.")
            continue

        if mentioned_user.id in mention_responses:
            await message.channel.send(mention_responses[mentioned_user.id])
            break

    await bot.process_commands(message)


token = os.getenv('DISCORD_TOKEN')
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set. Add it to .env before starting the bot.")

bot.run(token)
