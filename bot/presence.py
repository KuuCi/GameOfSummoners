# ─────────────────────────────────────────────
#  The Summoner's Court  ·  presence.py
# ─────────────────────────────────────────────

import discord
from bot.config import LOL_APP_NAME, IN_GAME_STATE

def is_in_lol_game(member: discord.Member) -> bool:
    for activity in member.activities:
        name = getattr(activity, "name", None)
        if not name or name.lower() != LOL_APP_NAME.lower():
            continue
        # Filter TFT first regardless of branch
        details = (getattr(activity, "details", None) or "").lower()
        if "teamfight" in details:
            continue
        act_state = getattr(activity, "state", None)
        if act_state and IN_GAME_STATE.lower() in act_state.lower():
            return True
        if details and IN_GAME_STATE.lower() in details:
            return True
    return False

def is_in_champ_select(member: discord.Member) -> bool:
    for activity in member.activities:
        name = getattr(activity, "name", None)
        if not name or name.lower() != LOL_APP_NAME.lower():
            continue
        state = (getattr(activity, "state", None) or "").lower()
        details = (getattr(activity, "details", None) or "").lower()
        combined = state + " " + details
        if "champion select" in combined or "matchmaking" in combined or "in queue" in combined:
            return True
    return False

def get_lol_activity(member: discord.Member) -> discord.Activity | None:
    for activity in member.activities:
        name = getattr(activity, "name", None)
        if name and name.lower() == LOL_APP_NAME.lower():
            return activity
    return None