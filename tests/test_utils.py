import unittest
from unittest.mock import patch
from commands import get_emote_url, player_str

class TestUtils(unittest.TestCase):

    def test_get_emote_url(self):
        self.assertEqual(
            get_emote_url("123456"),
            "https://raw.githubusercontent.com/deets-au/draftbot/main/wow_emotes/123456.png"
        )
        self.assertIsNone(get_emote_url(None))
        self.assertIsNone(get_emote_url(""))

    def test_player_str_captain(self):
        p = {"spec": "Captain", "name": "Dave"}
        self.assertEqual(player_str(p), "Dave (Captain / Leader)")

    def test_player_str_normal_no_emotes(self):
        p = {"name": "Deets", "spec": "Restoration1", "class": "Shaman"}
        self.assertEqual(player_str(p), "Deets (Restoration1)")

    @patch('commands.get_emote_url')
    def test_player_str_with_emotes(self, mock_get_url):
        mock_get_url.side_effect = lambda x: f"http://example.com/{x}.png" if x else None
        p = {
            "name": "Test",
            "spec": "Feral",
            "specEmoteId": "spec123",
            "roleEmoteId": "role456",
            "classEmoteId": "class789"
        }
        expected = "Test (Feral) [spec](http://example.com/spec123.png) [role](http://example.com/role456.png) [class](http://example.com/class789.png)"
        self.assertEqual(player_str(p), expected)