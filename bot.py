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
    "bhai chill kar 😂",
    "itna gussa kyu 😭",
    "language control bro 😤",
    "cool banne ki koshish fail 💀",
    "admin bulaun kya 👀"
]

mention_responses = {
    1476689941252800676: "so rhi hu",
    760729575789166652: "lmao ded 🤰‍♂️"
}

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  

    msg = message.content.lower()

    for word in bad_words:
        if word in msg:
            reply = random.choice(responses)
            await message.channel.send(f"{message.author.mention} {reply}")
            break

    if message.author.id == 760729575789166652 and msg == "soja morni":
        await message.channel.send("hap 🎀")
        await bot.close()
        return

    for mentioned_user in message.mentions:
        if mentioned_user.id in mention_responses:
            await message.channel.send(mention_responses[mentioned_user.id])
            break

    await bot.process_commands(message)

token = os.getenv('DISCORD_TOKEN')
if not token:
    raise RuntimeError("DISCORD_TOKEN is not set. Add it to .env before starting the bot.")

bot.run(token)
