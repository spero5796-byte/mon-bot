import discord
from discord.ext import commands
import os
from openai import OpenAI
from config import TOKEN, OPENAI_API_KEY, LOG_CHANNEL_ID, WARN_LIMIT

client_ai = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

warns = {}

def check_ai(text):
    try:
        r = client_ai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{
                "role": "user",
                "content": f"Répond OK ou BAD. BAD = insultes, toxicité, spam : {text}"
            }]
        )
        return "BAD" in r.choices[0].message.content
    except:
        return False

async def log(guild, msg):
    ch = guild.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send(msg)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id

    if check_ai(message.content):
        await message.delete()

        warns[uid] = warns.get(uid, 0) + 1

        await message.channel.send(
            f"⚠️ {message.author.mention} warn IA ({warns[uid]}/{WARN_LIMIT})"
        )

        await log(message.guild, f"Toxicité détectée: {message.author}")

        if warns[uid] >= WARN_LIMIT:
            try:
                await message.author.kick(reason="IA modération")
                await log(message.guild, f"Kick auto: {message.author}")
            except:
                pass

    await bot.process_commands(message)

bot.run(TOKEN)