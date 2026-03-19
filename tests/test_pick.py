import unittest
from unittest.mock import AsyncMock, patch
from commands import setup_commands

class MockBot:
    def __init__(self):
        self.drafts = {}

class MockContext:
    def __init__(self, channel_id=123, author_name="Dave"):
        self.channel = MagicMock(id=channel_id)
        self.author = MagicMock(display_name=author_name, name=author_name)
        self.send = AsyncMock()

class TestPick(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MockBot()
        setup_commands(self.bot)
        self.ctx = MockContext(author_name="Deets")

    def set_draft(self):
        self.bot.drafts["test"] = {
            "channel_id": 123,
            "captains": [{"name": "Deets", "userId": "123"}],
            "pool": [{"name": "Borsche", "class": "Druid", "spec": "Feral"}],
            "teams": {"Deets": [{"name": "Deets", "class": "Shaman", "spec": "Restoration"}]},
            "turn": 0,
            "direction": 1
        }

    async def test_pick_success(self):
        self.set_draft()
        await self.bot.get_command("pick")(self.ctx, query="Borsche")
        self.ctx.send.assert_any_call("**Deets** picked **Borsche (Druid - Feral)**!")
        self.assertEqual(len(self.bot.drafts["test"]["pool"]), 0)  # removed

    async def test_pick_wrong_turn(self):
        self.set_draft()
        self.ctx.author.display_name = "WrongUser"
        await self.bot.get_command("pick")(self.ctx, query="Borsche")
        self.ctx.send.assert_called_with("It's **Deets**'s turn — you can't pick right now.")