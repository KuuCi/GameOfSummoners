# ─────────────────────────────────────────────
#  The Summoner's Court  ·  state.py
# ─────────────────────────────────────────────

from typing import Dict, Any

# discord_id (str) → {
#   "riot_id":        str | None,      # None for non-League lords
#   "puuid":          str | None,
#   "summoner_id":    str | None,
#   "region":         str | None,
#   "house":          { name, motto, sigil, color, flavor },
#   "gold":           int,
#   "territory":      int,
#   "rank":           { tier, division, lp } | None,
#   "stats":          { wins, losses, pentas },
#   "titles":         [str],
#   "last_match_id":  str | None,
#   "backing":        str | None,      # discord_id of the lord they back
#   "active_wager":   { lord_id, outcome, amount } | None,
# }
user_data: Dict[str, Dict[str, Any]] = {}

# discord_id → timestamp when they went "In Game"
active_games: Dict[str, float] = {}

# pending duels: challenger_id → {
#   "target_id":  str,
#   "wager":      int,
#   "expires_at": float,
# }
pending_duels: Dict[str, Dict[str, Any]] = {}

# guild_id → channel_id for announcements
announcement_channels: Dict[str, int] = {}

# guild_id → channel_id for the Wall of Shame
shame_channels: Dict[str, int] = {}