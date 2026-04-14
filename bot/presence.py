# ─────────────────────────────────────────────
#  The Summoner's Court  ·  presence.py
# ─────────────────────────────────────────────

import discord
from bot.config import LOL_APP_NAME, IN_GAME_STATE

def is_in_lol_game(member: discord.Member) -> bool:
    """
    Return True if the member's Discord presence shows
    they are currently in a League of Legends game.
    """
    for activity in member.activities:
        if not isinstance(activity, discord.Activity):
            continue
        if activity.name and activity.name.lower() == LOL_APP_NAME.lower():
            # activity.state is "In Game" when a match is live
            if activity.state and IN_GAME_STATE.lower() in activity.state.lower():
                return True
    return False

def is_in_champ_select(member: discord.Member) -> bool:
    for activity in member.activities:
        if not isinstance(activity, discord.Activity):
            continue
        if activity.name and activity.name.lower() == LOL_APP_NAME.lower():
            state = (activity.state or "").lower()
            if "champion select" in state or "matchmaking" in state:
                return True
    return False

def get_lol_activity(member: discord.Member) -> discord.Activity | None:
    for activity in member.activities:
        if isinstance(activity, discord.Activity):
            if activity.name and activity.name.lower() == LOL_APP_NAME.lower():
                return activity
    return None
