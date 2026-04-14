# ─────────────────────────────────────────────
#  The Summoner's Court  ·  presence.py
# ─────────────────────────────────────────────

import discord
from bot.config import LOL_APP_NAME, IN_GAME_STATE

def is_in_lol_game(member: discord.Member) -> bool:
    """
    Return True if the member's Discord presence shows
    they are currently in a League of Legends game.
    Handles both discord.Activity (rich presence) and discord.Game.
    """
    for activity in member.activities:
        name = getattr(activity, "name", None)
        if not name:
            continue
        if name.lower() != LOL_APP_NAME.lower():
            continue

        # Rich presence (discord.Activity) — check state for "In Game"
        act_state = getattr(activity, "state", None)
        if act_state and IN_GAME_STATE.lower() in act_state.lower():
            return True

        # Also check details field — some clients put info there
        details = getattr(activity, "details", None)
        if details and IN_GAME_STATE.lower() in details.lower():
            return True

        # Basic game presence (discord.Game) — name matches but no state/details
        # Only count this if it's a Game type (not just in lobby)
        if isinstance(activity, discord.Game):
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