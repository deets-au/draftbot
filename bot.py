import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import json
import signal
import sys

from commands import setup_commands
from drafts import load_drafts, save_drafts

load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("ERROR: No TOKEN found in .env file!")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Attach drafts to bot object (Option 1 fix)
bot.drafts = load_drafts()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready! Use !startdraft in your test server.")
    # Reload drafts on ready (in case of external changes)
    bot.drafts = load_drafts()

# Graceful shutdown - save drafts
def shutdown(signal_received, frame):
    print("\nSIGINT or CTRL-C detected. Saving drafts and shutting down...")
    save_drafts(bot.drafts)
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

# Register commands from commands.py
setup_commands(bot)

bot.run(TOKEN)