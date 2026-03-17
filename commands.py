from discord.ext import commands
import discord
import aiohttp
import random
from api import fetch_event
from drafts import save_drafts

def get_emote_url(emote_id):
    if emote_id:
        return f"https://raw.githubusercontent.com/deets-au/draftbot/main/wow_emotes/{emote_id}.png"
    return None

def player_str(p):
    if p.get("spec") == "Captain":
        return f"{p['name']} (Captain / Leader)"
    
    parts = [p['name'], f"({p['spec']})"]
    
    spec_url = get_emote_url(p.get("specEmoteId"))
    if spec_url:
        parts.append(f"[spec]({spec_url})")
    
    role_url = get_emote_url(p.get("roleEmoteId"))
    if role_url:
        parts.append(f"[role]({role_url})")
    
    class_url = get_emote_url(p.get("classEmoteId"))
    if class_url:
        parts.append(f"[class]({class_url})")
    
    return " ".join(parts)

def setup_commands(bot):
    async def notify_turn(ctx, draft, turn_index):
        cap_dict = draft["captains"][turn_index]
        cap_name = cap_dict["name"]
        user_id = cap_dict.get("userId")
        
        mention = f"@{cap_name}"
        if user_id:
            try:
                user = await bot.fetch_user(int(user_id))
                mention = user.mention
            except:
                pass  # fallback

        await ctx.send(f"{mention} **your turn!** Pick a player with `!pick <name>`.\nRemaining: {len(draft['pool'])}")

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

        players = []
        for s in signups:
            if s.get("status") == "primary":
                players.append({
                    "name": s["name"],
                    "spec": s.get("specName", "Unknown"),
                    "role": s.get("roleName", "Unknown"),
                    "class": s.get("className", "Unknown"),
                    "userId": s.get("userId")
                })

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
            match = matches[0]
            captain_list.append({
                "name": match["name"],
                "userId": match["userId"]
            })

        pool = [p for p in players if p["name"] not in [c["name"] for c in captain_list]]
        random.shuffle(pool)

        draft = {
            "channel_id": ctx.channel.id,
            "event_id": event_id,
            "captains": captain_list,
            "pool": pool,
            "teams": {c["name"]: [{"name": c["name"], "spec": "Captain", "role": "Leader", "class": "Captain"}] for c in captain_list},
            "turn": 0,
            "direction": 1
        }

        bot.drafts[event_id] = draft
        save_drafts(bot.drafts)

        embed = discord.Embed(title=f"Draft Started – Event {event_id}", color=0x00aa88)
        embed.add_field(
            name="Captains & Starting Teams",
            value="\n".join(f"• **{c['name']}** (Team {c['name']} starts with captain themselves)" for c in captain_list),
            inline=False
        )
        embed.add_field(name="Remaining Players", value=len(pool), inline=True)
        embed.set_footer(text="Use !remaining • !pick <name> on your turn")
        await ctx.send(embed=embed)

        await notify_turn(ctx, draft, 0)

    @bot.command(name="pick")
    async def pick(ctx, *, query: str = None):
        if not query:
            await ctx.send("Usage: `!pick <part of player name>`")
            return

        event_id = next((eid for eid, d in bot.drafts.items() if d["channel_id"] == ctx.channel.id), None)
        if not event_id:
            await ctx.send("No active draft in this channel.")
            return

        draft = bot.drafts[event_id]
        current_cap_dict = draft["captains"][draft["turn"]]
        current_cap = current_cap_dict["name"]

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
            for cap_dict, team in draft["teams"].items():
                cap = cap_dict["name"]
                team_str = "\n".join(player_str(p) for p in team)
                embed.add_field(name=cap, value=team_str or "—", inline=False)
            await ctx.send(embed=embed)
            del bot.drafts[event_id]
            save_drafts(bot.drafts)
            return

        draft["turn"] += draft["direction"]
        if draft["turn"] >= len(draft["captains"]) or draft["turn"] < 0:
            draft["direction"] *= -1
            draft["turn"] += draft["direction"]

        save_drafts(bot.drafts)

        await notify_turn(ctx, draft, draft["turn"])

    @bot.command(name="adminpick")
    @commands.has_permissions(administrator=True)
    async def adminpick(ctx, *, query: str = None):
        if not query:
            await ctx.send("Usage: `!adminpick <part of player name>` (admin override)")
            return

        event_id = next((eid for eid, d in bot.drafts.items() if d["channel_id"] == ctx.channel.id), None)
        if not event_id:
            await ctx.send("No active draft in this channel.")
            return

        draft = bot.drafts[event_id]

        if not draft["pool"]:
            await ctx.send("No players left to pick.")
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

        current_cap_dict = draft["captains"][draft["turn"]]
        current_cap = current_cap_dict["name"]

        picked = matches[0]
        draft["pool"].remove(picked)
        draft["teams"][current_cap].append(picked)

        await ctx.send(f"**Admin override** — **{current_cap}** picked **{player_str(picked)}**!")

        if not draft["pool"]:
            embed = discord.Embed(title="Draft Complete!", color=0xff8800)
            for cap_dict, team in draft["teams"].items():
                cap = cap_dict["name"]
                team_str = "\n".join(player_str(p) for p in team)
                embed.add_field(name=cap, value=team_str or "—", inline=False)
            await ctx.send(embed=embed)
            del bot.drafts[event_id]
            save_drafts(bot.drafts)
            return

        draft["turn"] += draft["direction"]
        if draft["turn"] >= len(draft["captains"]) or draft["turn"] < 0:
            draft["direction"] *= -1
            draft["turn"] += draft["direction"]

        save_drafts(bot.drafts)

        await notify_turn(ctx, draft, draft["turn"])

    @bot.command(name="remaining")
    async def remaining(ctx):
        event_id = next((eid for eid, d in bot.drafts.items() if d["channel_id"] == ctx.channel.id), None)
        if not event_id:
            await ctx.send("No active draft here.")
            return

        draft = bot.drafts[event_id]
        if not draft["pool"]:
            await ctx.send("Pool is empty!")
            return

        class_dots = {
            "Priest": "⬜",
            "Shaman": "🟦",
            "Warrior": "🟫",
            "Druid": "🟧",
            "Mage": "🟦",
            "Paladin": "🩷",
            "Warlock": "🟪",
            "Hunter": "🟩",
            "Rogue": "🟨",
            "Unknown": "⬛"
        }

        embed = discord.Embed(
            title="Remaining Players",
            color=0x2f3136
        )

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
                f"{p['name']} ({p['spec'].rstrip('0123456789')})"  # strip trailing digits from spec
                for p in sorted_players
            ) or "—"

            embed.add_field(name=field_name, value=field_value, inline=True)

        by_role = {}
        for p in draft["pool"]:
            role = p.get("role", "Unknown")
            if role in ["Tanks", "Healers"]:
                by_role.setdefault(role, []).append(p)

        for role, players in sorted(by_role.items()):
            field_name = f"**{role} ({len(players)})**"

            sorted_players = sorted(players, key=lambda x: x["name"])
            field_value = "\n".join(
                f"{p['name']} ({p['spec'].rstrip('0123456789')})"  # strip trailing digits from spec
                for p in sorted_players
            ) or "—"

            embed.add_field(name=field_name, value=field_value, inline=True)

        embed.set_footer(text=f"Total unique players: {len(draft['pool'])} • Pick with !pick <name>")
        await ctx.send(embed=embed)

    @bot.command(name="teams")
    async def teams(ctx):
        event_id = next((eid for eid, d in bot.drafts.items() if d["channel_id"] == ctx.channel.id), None)
        if not event_id:
            await ctx.send("No active draft here.")
            return

        draft = bot.drafts[event_id]

        embed = discord.Embed(
            title="Current Teams",
            color=0x2f3136
        )

        # Build global pick order (non-captains in the order they were picked)
        global_pick_order = []
        for team in draft["teams"].values():
            global_pick_order.extend(team[1:])

        pick_number_map = {}
        for i, p in enumerate(global_pick_order, 1):
            pick_number_map[p["name"]] = i

        for cap_name, team in draft["teams"].items():
            team_lines = []

            # Captain first - same format as others
            cap_class = team[0].get("class", "Captain")
            cap_spec = team[0].get("spec", "Leader").rstrip('0123456789')  # strip trailing digits
            team_lines.append(f"**{cap_name}** ({cap_class} - {cap_spec})")

            # Picked players with global draft order number
            for p in team[1:]:
                pick_num = pick_number_map.get(p["name"], "?")
                spec_clean = p['spec'].rstrip('0123456789')  # strip trailing digits
                line = f"{pick_num}: {p['name']} ({p['class']} - {spec_clean})"
                team_lines.append(line)

            embed.add_field(
                name=f"Team {cap_name}",
                value="\n".join(team_lines) or "— (empty)",
                inline=True
            )

        embed.set_footer(text=f"Total players assigned: {sum(len(t) for t in draft['teams'].values())} • Pick with !pick <name>")
        await ctx.send(embed=embed)

    @bot.command(name="status")
    async def status(ctx):
        event_id = next((eid for eid, d in bot.drafts.items() if d["channel_id"] == ctx.channel.id), None)
        if not event_id:
            await ctx.send("No active draft here.")
            return

        draft = bot.drafts[event_id]
        current = draft["captains"][draft["turn"]]["name"]
        embed = discord.Embed(title="Draft Status")
        embed.add_field(name="Current Turn", value=current, inline=False)
        embed.add_field(name="Remaining", value=len(draft["pool"]), inline=True)
        embed.add_field(name="Teams", value=len(draft["teams"]), inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="cleardrafts")
    @commands.has_permissions(administrator=True)
    async def cleardrafts(ctx):
        if not bot.drafts:
            await ctx.send("No active drafts to clear.")
            return

        old_count = len(bot.drafts)
        bot.drafts = {}
        save_drafts(bot.drafts)
        await ctx.send(f"Cleared **{old_count}** active draft(s). Ready for a new one!")

    @bot.command(name="enddraft")
    @commands.has_permissions(administrator=True)
    async def enddraft(ctx):
        event_id = next((eid for eid, d in bot.drafts.items() if d["channel_id"] == ctx.channel.id), None)
        if not event_id:
            await ctx.send("No active draft in this channel.")
            return

        del bot.drafts[event_id]
        save_drafts(bot.drafts)
        await ctx.send(f"Draft for event {event_id} has been ended/cancelled.")