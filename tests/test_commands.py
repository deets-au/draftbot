import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from discord.ext import commands
import discord

# Mock the bot and ctx
class MockBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!")
        self.drafts = {}

class MockContext:
    def __init__(self, channel_id=123, guild_id=456, author=None):
        self.channel = MagicMock(id=channel_id)
        self.guild = MagicMock(id=guild_id)
        self.author = author or MagicMock(display_name="TestUser", name="testuser")
        self.send = AsyncMock()

# Import your setup function
from commands import setup_commands, player_str

class TestCommands(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.bot = MockBot()
        setup_commands(self.bot)
        self.ctx = MockContext(channel_id=123456, guild_id=789012)

    def test_player_str(self):
        p = {"name": "Deets", "spec": "Restoration1", "class": "Shaman"}
        self.assertEqual(player_str(p), "Deets (Restoration1)")

    async def test_startdraft_basic(self):
        # Mock fetch_event
        with patch('commands.fetch_event', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ({
                "signUps": [
                    {"name": "Deets", "specName": "Restoration1", "roleName": "Healers", "className": "Shaman", "userId": "123", "status": "primary"},
                    {"name": "Zylaria", "specName": "Holy", "roleName": "Healers", "className": "Priest", "userId": "456", "status": "primary"}
                ]
            }, None)

            await self.bot.get_command("startdraft")(self.ctx, "12345", "Deets", "Zylaria")

            self.ctx.send.assert_called()
            draft = self.bot.drafts["12345"]
            self.assertEqual(len(draft["captains"]), 2)
            self.assertEqual(draft["captains"][0]["name"], "Deets")
            self.assertEqual(draft["pool"][0]["class"], "Shaman")  # example check

    async def test_remaining_no_draft(self):
        await self.bot.get_command("remaining")(self.ctx)
        self.ctx.send.assert_called_with("No active draft here.")

    async def test_remaining_empty_pool(self):
        self.bot.drafts["test"] = {"channel_id": self.ctx.channel.id, "pool": []}
        await self.bot.get_command("remaining")(self.ctx)
        self.ctx.send.assert_called_with("Pool is empty!")

    # Add more tests as needed (e.g. pick logic, adminpick, etc.)