import atexit

import discord
from discord.ext import commands
from dotenv import load_dotenv

from drafts import drafts, save_drafts, reload_drafts
from commands import setup as setup_commands

load_dotenv()
TOKEN = __import__("os").getenv("TOKEN")

if not TOKEN:
    print("ERROR: No TOKEN found in .env file!")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def _save_drafts_on_exit() -> None:
    """Persist drafts to disk when the process exits."""
    print("[INFO] Saving drafts to disk...")
    save_drafts(drafts)


atexit.register(_save_drafts_on_exit)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready! Use !startdraft in your test server.")

    # Reload drafts on startup in case they were modified externally
    reload_drafts()


@bot.event
async def on_command_error(ctx, error):
    print(f"[ERROR] Command error in {ctx.command}: {error}")
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(f"Error: {str(error)}")


setup_commands(bot)

bot.run(TOKEN)
