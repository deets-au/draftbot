"""Command implementations for the DraftBot."""

import random

import discord
from discord.ext import commands

from drafts import drafts, save_drafts, get_draft_by_channel
from api import fetch_event, make_discord_emoji


def player_str(p):
    if p.get("spec") == "Captain":
        return f"{p['name']} (Captain / Leader)"
    cls = p.get("class", "Unknown")
    return f"{p['name']} ({p['spec']} - {p['role']} - {cls})"


@commands.command(name="hello")
async def hello(ctx):
    await ctx.send("Hello! Bot is alive.")


@commands.command(name="startdraft")
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
            spec_emoji = make_discord_emoji(s.get("specName", ""), s.get("specEmoteId", ""))

            players.append({
                "name": s["name"],
                "spec": s.get("specName", "Unknown"),
                "specEmoji": spec_emoji,
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
        "event_data": data,
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


@commands.command(name="pick")
async def pick(ctx, *, query: str = None):
    if not query:
        await ctx.send("Usage: `!pick <part of player name>`")
        return

    draft = get_draft_by_channel(ctx.channel.id)
    if not draft:
        await ctx.send("No active draft in this channel.")
        return

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
        del drafts[draft["event_id"]]
        save_drafts(drafts)
        return

    draft["turn"] += draft["direction"]
    if draft["turn"] >= len(draft["captains"]) or draft["turn"] < 0:
        draft["direction"] *= -1
        draft["turn"] += draft["direction"]

    save_drafts(drafts)

    next_cap = draft["captains"][draft["turn"]]
    await ctx.send(f"Next turn: **{next_cap}**")


@commands.command(name="remaining")
async def remaining(ctx):
    draft = get_draft_by_channel(ctx.channel.id)
    if not draft:
        await ctx.send("No active draft here.")
        return

    if not draft["pool"]:
        await ctx.send("Pool is empty!")
        return

    embed = discord.Embed(
        title="Remaining Players",
        color=0x2f3136  # dark grey background
    )

    # ── Class groups (inline) ─────────────────────────────────────────────────
    by_class = {}
    for p in draft["pool"]:
        cls = p.get("class", "Unknown")
        by_class.setdefault(cls, []).append(p)

    for cls, players in sorted(by_class.items()):
        field_name = f"**{cls} ({len(players)})**"

        sorted_players = sorted(players, key=lambda x: x["name"])
        field_value = "\n".join(
            f"{p.get('specEmoji','')} {p['name']}"
            for p in sorted_players
        ) or "—"

        embed.add_field(name=field_name, value=field_value, inline=True)

    # ── Tanks and Healers (inline) ─────────────────────────────────────────────
    by_role = {}
    for p in draft["pool"]:
        role = p.get("role", "Unknown")
        if role in ["Tanks", "Healers"]:
            by_role.setdefault(role, []).append(p)

    for role, players in sorted(by_role.items()):
        field_name = f"**{role} ({len(players)})**"

        sorted_players = sorted(players, key=lambda x: x["name"])
        field_value = "\n".join(
            f"{p.get('specEmoji','')} {p['name']}"
            for p in sorted_players
        ) or "—"

        embed.add_field(name=field_name, value=field_value, inline=True)

    embed.set_footer(text=f"Total unique players: {len(draft['pool'])} • Pick with !pick <name>")
    await ctx.send(embed=embed)


@commands.command(name="teams")
async def teams(ctx):
    draft = get_draft_by_channel(ctx.channel.id)
    if not draft:
        await ctx.send("No active draft here.")
        return

    embed = discord.Embed(title="Current Teams")
    for cap, team in draft["teams"].items():
        embed.add_field(name=cap, value="\n".join(player_str(p) for p in team), inline=False)
    await ctx.send(embed=embed)


@commands.command(name="status")
async def status(ctx):
    draft = get_draft_by_channel(ctx.channel.id)
    if not draft:
        await ctx.send("No active draft here.")
        return

    current = draft["captains"][draft["turn"]]
    embed = discord.Embed(title="Draft Status")
    embed.add_field(name="Current Turn", value=current, inline=False)
    embed.add_field(name="Remaining", value=len(draft["pool"]), inline=True)
    embed.add_field(name="Teams", value=len(draft["teams"]), inline=True)
    await ctx.send(embed=embed)


def setup(bot):
    """Register commands on the bot instance."""
    bot.add_command(hello)
    bot.add_command(startdraft)
    bot.add_command(pick)
    bot.add_command(remaining)
    bot.add_command(teams)
    bot.add_command(status)
