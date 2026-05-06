import discord
import os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print("BOT CONNECTÉ")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    print("MESSAGE RECU:", message.content)

    if "pute" in message.content.lower():
        print("INSULTE DETECTÉE")
        await message.channel.send("⚠️ insulte détectée")

bot.run(TOKEN)
