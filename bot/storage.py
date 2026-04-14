# ─────────────────────────────────────────────
#  The Summoner's Court  ·  storage.py
# ─────────────────────────────────────────────

import json
import os

DATA_FILE = "data/kingdom.json"

def _ensure_dir() -> None:
    os.makedirs("data", exist_ok=True)

def load() -> dict:
    _ensure_dir()
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save(data: dict) -> None:
    _ensure_dir()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_channels() -> dict:
    _ensure_dir()
    path = "data/channels.json"
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

def save_channels(data: dict) -> None:
    _ensure_dir()
    with open("data/channels.json", "w") as f:
        json.dump(data, f, indent=2)

def load_all_state(user_data: dict, announcement_channels: dict, shame_channels: dict) -> None:
    raw = load()
    user_data.update(raw.get("users", {}))
    ch = load_channels()
    announcement_channels.update(ch.get("announcements", {}))
    shame_channels.update(ch.get("shame", {}))

def persist_all(user_data: dict, announcement_channels: dict, shame_channels: dict) -> None:
    save({"users": dict(user_data)})
    save_channels({
        "announcements": dict(announcement_channels),
        "shame": dict(shame_channels),
    })

def adjust_gold(user_data: dict, discord_id: str, amount: int) -> int:
    user = user_data[discord_id]
    user["gold"] = max(0, user["gold"] + amount)
    return user["gold"]