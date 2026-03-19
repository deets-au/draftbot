import unittest
from unittest.mock import AsyncMock, patch
from commands import setup_commands

class MockBot:
    def __init__(self):
        self.drafts = {}
        self.send = AsyncMock()

class MockContext:
    def __init__(self, channel_id=123, guild_id=456):
        self.channel = MagicMock(id=channel_id)
        self.guild = MagicMock(id=guild_id)
        self.send = AsyncMock()

class TestStartDraft(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MockBot()
        setup_commands(self.bot)
        self.ctx = MockContext()

    @patch('commands.fetch_event')
    async def test_startdraft_success(self, mock_fetch):
        mock_fetch.return_value = ({
            "signUps": [
                {"name": "Deets", "specName": "Restoration1", "roleName": "Healers", "className": "Shaman", "userId": "123", "status": "primary"},
                {"name": "Zylaria", "specName": "Holy", "roleName": "Healers", "className": "Priest", "userId": "456", "status": "primary"}
            ]
        }, None)

        await self.bot.get_command("startdraft")(self.ctx, "event123", "Deets", "Zylaria")

        self.ctx.send.assert_called()
        draft = self.bot.drafts["event123"]
        self.assertEqual(len(draft["captains"]), 2)
        self.assertEqual(draft["captains"][0]["name"], "Deets")
        self.assertEqual(draft["pool"][0]["class"], "Shaman")  # example

    @patch('commands.fetch_event')
    async def test_startdraft_not_enough_players(self, mock_fetch):
        mock_fetch.return_value = ({"signUps": [{"name": "One", "status": "primary"}]}, None)
        await self.bot.get_command("startdraft")(self.ctx, "event123", "One", "Two")
        self.ctx.send.assert_called_with("Not enough players (1) for 2 teams.")