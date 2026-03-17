# Draftbot

A simple Discord bot to manage raid drafts using the Raid Helper API.

## Setup

1. **Create a virtual environment** (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. **Install dependencies**:

```powershell
pip install -r requirements.txt
```

3. **Create a `.env` file** with your Discord bot token:

```
TOKEN=your_discord_bot_token_here
```

4. **Run the bot**:

```powershell
python bot.py
```

## Commands

- `!hello` - Check that the bot is running.
- `!startdraft <event_id> <Captain1> <Captain2> ...` - Start a draft for a raid event.
- `!pick <player name>` - Pick a player when it is your turn.
- `!remaining` - Show remaining players in the draft.
- `!teams` - Show the current teams.
- `!status` - Show the draft status (current turn, remaining pool, teams).

## Notes

- `drafts.json` is used to persist draft state across restarts and is ignored by git.
- Make sure `MESSAGE CONTENT INTENT` is enabled in the Discord Developer Portal for your bot.
