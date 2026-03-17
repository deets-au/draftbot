import atexit
import discord
from discord.ext import commands
import aiohttp
import json
import os
import random
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")


def _save_drafts_on_exit() -> None:
    """Persist drafts to disk when the process exits."""
    print("[INFO] Saving drafts to disk...")
    save_drafts(drafts)

atexit.register(_save_drafts_on_exit)

if not TOKEN:
    print("ERROR: No TOKEN found in .env file!")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "drafts.json"

def load_drafts():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_drafts(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

drafts = load_drafts()

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

def player_str(p):
    if p.get("spec") == "Captain":
        return f"{p['name']} (Captain / Leader)"
    cls = p.get("class", "Unknown")
    return f"{p['name']} ({p['spec']} - {p['role']} - {cls})"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready! Use !startdraft in your test server.")
    global drafts
    drafts = load_drafts()

@bot.event
async def on_command_error(ctx, error):
    print(f"[ERROR] Command error in {ctx.command}: {error}")
    if isinstance(error, commands.CommandNotFound):
        return
    await ctx.send(f"Error: {str(error)}")

@bot.command(name="hello")
async def hello(ctx):
    await ctx.send("Hello! Bot is alive.")

@bot.command(name="startdraft")
async def startdraft(ctx, event_id: str = None, *captain_names: str):
    if not event_id:
        await ctx.send("Usage: `!startdraft <eventid> Captain1 Captain2 ...`")
        return

    if len(captain_names) < 2:
        await ctx.send("You need at least 2 captains.")
        return

    data, err = await fetch_event(event_id)
    if err:
        await ctx.send(f"Failed to fetch event: {err}")
        return

    signups = data.get("signUps", [])
    if not signups:
        await ctx.send("No sign-ups found in this event.")
        return

    # Build class lookup: emoteId → class name
    class_lookup = {}
    for cls in data.get("classes", []):
        emote = cls.get("emoteId")
        if emote:
            class_lookup[emote] = cls.get("name", "Unknown")

    # Build players with correct class name
    players = []
    for s in signups:
        if s.get("status") == "primary":
            class_emoji = s.get("classEmoteId")
            class_name = class_lookup.get(class_emoji, "Unknown")

            players.append({
                "name": s["name"],
                "spec": s.get("specName", "Unknown"),
                "role": s.get("roleName", "Unknown"),
                "class": class_name,
                "userId": s.get("userId")
            })

    print(f"[DEBUG] Loaded {len(players)} players with classes: {set(p['class'] for p in players)}")

    if len(players) < len(captain_names) + 5:
        await ctx.send(f"Not enough players ({len(players)}) for {len(captain_names)} teams.")
        return

    captain_list = []
    for cap in captain_names:
        cap_lower = cap.lower()
        matches = [p for p in players if cap_lower in p["name"].lower()]
        if not matches:
            await ctx.send(f"Captain '{cap}' not found in sign-ups.")
            return
        if len(matches) > 1:
            names = ", ".join(m["name"] for m in matches[:3])
            await ctx.send(f"Multiple matches for '{cap}': {names}\nBe more specific.")
            return
        captain_list.append(matches[0]["name"])

    pool = [p for p in players if p["name"] not in captain_list]
    random.shuffle(pool)

    draft = {
        "channel_id": ctx.channel.id,
        "event_id": event_id,
        "captains": captain_list,
        "pool": pool,
        "teams": {c: [{"name": c, "spec": "Captain", "role": "Leader", "class": "Captain"}] for c in captain_list},
        "turn": 0,
        "direction": 1
    }

    drafts[event_id] = draft
    save_drafts(drafts)

    embed = discord.Embed(title=f"Draft Started – Event {event_id}", color=0x00aa88)
    embed.add_field(
        name="Captains & Starting Teams",
        value="\n".join(f"• **{c}** (Team {c} starts with captain themselves)" for c in captain_list),
        inline=False
    )
    embed.add_field(name="Remaining Players", value=len(pool), inline=True)
    embed.set_footer(text="Use !remaining • !pick <name> on your turn")
    await ctx.send(embed=embed)

    first_cap = captain_list[0]
    await ctx.send(f"**Round 1 – {first_cap}** your turn! (Your team already has you as captain)")

@bot.command(name="pick")
async def pick(ctx, *, query: str = None):
    if not query:
        await ctx.send("Usage: `!pick <part of player name>`")
        return

    event_id = next((eid for eid, d in drafts.items() if d["channel_id"] == ctx.channel.id), None)
    if not event_id:
        await ctx.send("No active draft in this channel.")
        return

    draft = drafts[event_id]
    current_cap = draft["captains"][draft["turn"]]

    if ctx.author.display_name != current_cap and ctx.author.name != current_cap:
        await ctx.send(f"It's **{current_cap}**'s turn — you can't pick right now.")
        return

    q = query.lower().strip()
    matches = [p for p in draft["pool"] if q in p["name"].lower()]

    if not matches:
        await ctx.send(f"No player found matching '{query}'.\nTry `!remaining`.")
        return

    if len(matches) > 1:
        names = "\n".join(f"- {player_str(m)}" for m in matches[:6])
        await ctx.send(f"Multiple matches:\n{names}\nBe more specific.")
        return

    picked = matches[0]
    draft["pool"].remove(picked)
    draft["teams"][current_cap].append(picked)

    await ctx.send(f"**{current_cap}** picked **{player_str(picked)}**!")

    if not draft["pool"]:
        embed = discord.Embed(title="Draft Complete!", color=0xff8800)
        for cap, team in draft["teams"].items():
            team_str = "\n".join(player_str(p) for p in team)
            embed.add_field(name=cap, value=team_str or "—", inline=False)
        await ctx.send(embed=embed)
        del drafts[event_id]
        save_drafts(drafts)
        return

    draft["turn"] += draft["direction"]
    if draft["turn"] >= len(draft["captains"]) or draft["turn"] < 0:
        draft["direction"] *= -1
        draft["turn"] += draft["direction"]

    save_drafts(drafts)

    next_cap = draft["captains"][draft["turn"]]
    await ctx.send(f"Next turn: **{next_cap}**")

@bot.command(name="remaining")
async def remaining(ctx):
    event_id = next((eid for eid, d in drafts.items() if d["channel_id"] == ctx.channel.id), None)
    if not event_id:
        await ctx.send("No active draft here.")
        return

    draft = drafts[event_id]
    if not draft["pool"]:
        await ctx.send("Pool is empty!")
        return

    # Coloured emoji squares for class headings
    class_dots = {
        "Priest": "⬜",
        "Shaman": "🟦",
        "Warrior": "🟫",
        "Druid": "🟧",
        "Mage": "🟦",
        "Paladin": "🩷",      # ← Lighter pink!
        "Warlock": "🟪",
        "Hunter": "🟩",
        "Rogue": "🟨",
        "Unknown": "⬛"
    }

    embed = discord.Embed(
        title="Remaining Players",
        color=0x2f3136  # dark grey background
    )

    # ── Class groups (inline) ─────────────────────────────────────────────────
    by_class = {}
    for p in draft["pool"]:
        cls = p.get("class", "Unknown")
        if cls in class_dots:
            by_class.setdefault(cls, []).append(p)

    for cls, players in sorted(by_class.items()):
        dot = class_dots[cls]
        field_name = f"{dot} **{cls} ({len(players)})**"

        sorted_players = sorted(players, key=lambda x: x["name"])
        field_value = "\n".join(
            f"{p['name']} ({p['spec']})"
            for p in sorted_players
        ) or "—"

        embed.add_field(name=field_name, value=field_value, inline=True)

    # ── Tanks and Healers (inline, no colour/dot) ─────────────────────────────
    by_role = {}
    for p in draft["pool"]:
        role = p.get("role", "Unknown")
        if role in ["Tanks", "Healers"]:
            by_role.setdefault(role, []).append(p)

    for role, players in sorted(by_role.items()):
        field_name = f"**{role} ({len(players)})**"

        sorted_players = sorted(players, key=lambda x: x["name"])
        field_value = "\n".join(
            f"{p['name']} ({p['spec']})"
            for p in sorted_players
        ) or "—"

        embed.add_field(name=field_name, value=field_value, inline=True)

    embed.set_footer(text=f"Total unique players: {len(draft['pool'])} • Pick with !pick <name>")
    await ctx.send(embed=embed)

@bot.command(name="teams")
async def teams(ctx):
    event_id = next((eid for eid, d in drafts.items() if d["channel_id"] == ctx.channel.id), None)
    if not event_id:
        await ctx.send("No active draft here.")
        return

    draft = drafts[event_id]
    embed = discord.Embed(title="Current Teams")
    for cap, team in draft["teams"].items():
        embed.add_field(name=cap, value="\n".join(player_str(p) for p in team), inline=False)
    await ctx.send(embed=embed)

@bot.command(name="status")
async def status(ctx):
    event_id = next((eid for eid, d in drafts.items() if d["channel_id"] == ctx.channel.id), None)
    if not event_id:
        await ctx.send("No active draft here.")
        return

    draft = drafts[event_id]
    current = draft["captains"][draft["turn"]]
    embed = discord.Embed(title="Draft Status")
    embed.add_field(name="Current Turn", value=current, inline=False)
    embed.add_field(name="Remaining", value=len(draft["pool"]), inline=True)
    embed.add_field(name="Teams", value=len(draft["teams"]), inline=True)
    await ctx.send(embed=embed)

bot.run(TOKEN)