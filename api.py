"""API helpers for fetching event data and building emoji strings."""

import re
import aiohttp


def make_discord_emoji(name: str, emote_id: str) -> str:
    """Build a Discord custom emoji string from name + emote ID."""
    if not name or not emote_id:
        return ""

    safe = re.sub(r"[^0-9A-Za-z_]", "_", name)
    return f"<:{safe}:{emote_id}>"


async def fetch_event(event_id: str):
    url = f"https://raid-helper.dev/api/v2/events/{event_id}"
    print(f"[DEBUG] Fetching event from: {url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            print(f"[DEBUG] API response status: {resp.status}")
            if resp.status != 200:
                return None, f"API returned HTTP {resp.status}"
            try:
                data = await resp.json()
                print(f"[DEBUG] API returned data with {len(data.get('signUps', []))} signups")
                return data, None
            except Exception as e:
                return None, f"JSON parse error: {str(e)}"
