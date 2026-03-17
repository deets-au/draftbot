"""Draft persistence and helper utilities."""

import json
import os

DATA_FILE = "drafts.json"


def load_drafts():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            # If the file is empty/corrupt, reset it safely.
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                f.write("{}")
            return {}
    return {}


def save_drafts(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# State (loaded on import)
drafts = load_drafts()


def reload_drafts():
    """Reload drafts from disk into the module state."""
    global drafts
    drafts = load_drafts()
    return drafts


def get_draft_by_channel(channel_id):
    """Return the draft stored for a given channel, or None."""
    return next((d for d in drafts.values() if d.get("channel_id") == channel_id), None)


def get_event_data_for_draft(draft):
    """Return the raw event payload stored in a draft."""
    return (draft or {}).get("event_data")


def get_signups_for_draft(draft):
    """Return the list of signups for a draft event."""
    return get_event_data_for_draft(draft).get("signUps", []) if get_event_data_for_draft(draft) else []


def get_classes_for_draft(draft):
    """Return the list of classes for a draft event."""
    return get_event_data_for_draft(draft).get("classes", []) if get_event_data_for_draft(draft) else []


def clear_drafts():
    """Clear all in-memory drafts and reset persistence file."""
    global drafts
    drafts = {}
    save_drafts(drafts)
    return drafts
