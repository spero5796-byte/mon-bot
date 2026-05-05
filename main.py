import discord
import os
from openai import OpenAI

TOKEN = os.getenv("DISCORD_TOKEN")
client_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

# 🧠 IA CHECK
def is_toxic(text):
    try:
        response = client_ai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{
                "role": "user",
                "content": f"""
Analyse ce message Discord.

Répond seulement :
YES ou NO

YES = insultes, haine, sexualité choquante, harcèlement, spam
NO = normal

Message: {text}
"""
            }]
        )

        result = response.choices[0].message.content.strip()
        return result == "YES"

    except:
        return False

# 🚨 MODERATION
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if is_toxic(message.content):
        await message.delete()
        await message.channel.send(
            f"⚠️ {message.author.mention} message supprimé par IA"
        )
        return

    if message.content == "!ping":
        await message.channel.send("pong")

# 🔵 READY
@bot.event
async def on_ready():
    print(f"Bot IA connecté : {bot.user}")

bot.run(TOKEN)
