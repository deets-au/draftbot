import unittest
from unittest.mock import AsyncMock, patch
import discord
from discord.ext import commands
from commands import setup_commands
from unittest.mock import AsyncMock, MagicMock, patch

class TestRemaining(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.bot.drafts = {}  # mock state
        setup_commands(self.bot)  # register commands
        self.ctx = MagicMock()
        self.ctx.channel = MagicMock(id=123456)
        self.ctx.send = AsyncMock()

    def create_draft(self):
        self.bot.drafts["test"] = {
            "channel_id": 123456,
            "pool": [
                {"name": "Deets", "spec": "Restoration1", "class": "Shaman", "role": "Healers"},
                {"name": "Borsche", "spec": "Feral", "class": "Druid", "role": "Melee"},
                {"name": "Blockaroach", "spec": "Holy1", "class": "Paladin", "role": "Healers"},
                {"name": "Sid", "spec": "Protection1", "class": "Warrior", "role": "Tanks"},
            ],
            "teams": {}
        }

    async def test_remaining_no_draft(self):
        command = self.bot.get_command("remaining")
        self.assertIsNotNone(command, "Command 'remaining' not registered - check setup_commands")
        await command.invoke(self.ctx)
        self.ctx.send.assert_called_with("No active draft here.")

    async def test_remaining_empty_pool(self):
        self.bot.drafts["test"] = {"channel_id": 123456, "pool": []}
        command = self.bot.get_command("remaining")
        self.assertIsNotNone(command, "Command 'remaining' not registered")
        await command.invoke(self.ctx)
        self.ctx.send.assert_called_with("Pool is empty!")

    async def test_remaining_spec_stripping(self):
        self.create_draft()
        command = self.bot.get_command("remaining")
        self.assertIsNotNone(command, "Command 'remaining' not registered")
        await command.invoke(self.ctx)
        self.ctx.send.assert_called_once()
        embed = self.ctx.send.call_args[0][0]
        self.assertIsInstance(embed, discord.Embed)
        self.assertEqual(embed.title, "Remaining Players")
        embed_str = str(embed)
        self.assertIn("Deets (Restoration)", embed_str)  # stripped
        self.assertIn("Blockaroach (Holy)", embed_str)   # stripped