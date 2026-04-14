# ─────────────────────────────────────────────
#  The Summoner's Court  ·  kingdom.py
# ─────────────────────────────────────────────

import random
from bot.config import (
    STARTING_GOLD, HOUSE_ADJECTIVES, HOUSE_NOUNS, HOUSE_MOTTOS,
    SHAME_TITLES, GLORY_TITLES, WIN_GOLD, LOSS_GOLD, SURRENDER_PENALTY,
    PENTA_BONUS, RANK_UP_BONUS, RANK_DOWN_PENALTY, TERRITORY_PER_WIN,
    BACKER_WIN_SHARE, BACKER_LOSS_SHARE, BACKER_PENTA_BONUS,
)

SIGILS = [
    "⚔️", "🛡️", "🐉", "🔥", "💀", "🌑", "⚡", "🗡️", "🏹", "🌊",
    "🐺", "🦅", "🌙", "☄️", "🩸", "🧿", "🔮", "👁️", "🦂", "🪓",
]

HOUSE_COLORS = [
    0xC0392B, 0x8E44AD, 0x2980B9, 0x27AE60, 0xF39C12,
    0x1ABC9C, 0xE74C3C, 0x3498DB, 0xD35400, 0x7F8C8D,
]

def generate_house(champion_pool: list[str]) -> dict:
    adj   = random.choice(HOUSE_ADJECTIVES)
    noun  = random.choice(HOUSE_NOUNS)
    name  = f"House {adj} {noun}"
    motto = random.choice(HOUSE_MOTTOS)
    sigil = random.choice(SIGILS)
    color = random.choice(HOUSE_COLORS)
    if champion_pool:
        champs = ", ".join(champion_pool[:3])
        flavor = f"Forged in the shadow of {champs}."
    else:
        flavor = "Their origins are shrouded in mystery."
    return {"name": name, "motto": motto, "sigil": sigil, "color": color, "flavor": flavor}

def new_user_entry(riot_id: str, puuid: str, summoner_id: str,
                   region: str, house: dict, rank: dict | None) -> dict:
    tier     = rank.get("tier", "UNRANKED")    if rank else "UNRANKED"
    division = rank.get("rank", "")            if rank else ""
    lp       = rank.get("leaguePoints", 0)     if rank else 0
    return {
        "riot_id":       riot_id,
        "puuid":         puuid,
        "summoner_id":   summoner_id,
        "region":        region,
        "house":         house,
        "gold":          STARTING_GOLD,
        "territory":     0,
        "rank":          {"tier": tier, "division": division, "lp": lp},
        "stats":         {"wins": 0, "losses": 0, "pentas": 0, "joust_wins": 0, "joust_losses": 0},
        "titles":        [],
        "shame":         None,   # Active shame title string, or None. Cleared on joust win.
        "last_match_id": None,
        "backing":       None,
        "active_wager":  None,
    }

def apply_match_result(user: dict, participant: dict, game_duration: int) -> dict:
    won       = participant.get("win", False)
    penta     = participant.get("pentaKills", 0) > 0
    surrender = game_duration < 20 * 60 and not won
    delta     = WIN_GOLD if won else LOSS_GOLD
    reasons   = []

    if won:
        user["stats"]["wins"] += 1
        user["territory"] += TERRITORY_PER_WIN
        reasons.append(f"+{WIN_GOLD} (victory)")
    else:
        user["stats"]["losses"] += 1
        reasons.append(f"{LOSS_GOLD} (defeat)")
        if surrender:
            delta += SURRENDER_PENALTY
            reasons.append(f"{SURRENDER_PENALTY} (early surrender dishonor)")

    if penta:
        delta += PENTA_BONUS
        user["stats"]["pentas"] += 1
        reasons.append(f"+{PENTA_BONUS} 💥 PENTAKILL")

    user["gold"] = max(0, user["gold"] + delta)
    return {"won": won, "delta": delta, "reasons": reasons, "penta": penta}

def apply_backing_result(backer: dict, won: bool, penta: bool) -> dict:
    """Apply gold change to a lord who is backing another lord."""
    delta   = BACKER_WIN_SHARE if won else BACKER_LOSS_SHARE
    reasons = []
    if won:
        reasons.append(f"+{BACKER_WIN_SHARE} (backed lord's victory)")
    else:
        reasons.append(f"{BACKER_LOSS_SHARE} (backed lord's defeat)")
    if penta:
        delta += BACKER_PENTA_BONUS
        reasons.append(f"+{BACKER_PENTA_BONUS} (backed lord's PENTAKILL)")
    backer["gold"] = max(0, backer["gold"] + delta)
    return {"delta": delta, "reasons": reasons}

def resolve_wager(backer: dict, won_game: bool) -> dict | None:
    """Resolve a lord's active wager. Returns result dict or None if no wager."""
    wager = backer.get("active_wager")
    if not wager:
        return None
    amount  = wager["amount"]
    correct = (wager["outcome"] == "win") == won_game
    if correct:
        backer["gold"] = max(0, backer["gold"] + amount * 2)
    else:
        backer["gold"] = max(0, backer["gold"] - amount)
    backer["active_wager"] = None
    return {"correct": correct, "amount": amount, "outcome": wager["outcome"]}

def apply_rank_change(user: dict, new_rank: dict | None) -> dict | None:
    if not new_rank or not user.get("rank"):
        return None
    old      = user["rank"]
    new_tier = new_rank.get("tier", "UNRANKED")
    new_div  = new_rank.get("rank", "")
    new_lp   = new_rank.get("leaguePoints", 0)

    TIER_ORDER = ["IRON","BRONZE","SILVER","GOLD","PLATINUM","EMERALD","DIAMOND",
                  "MASTER","GRANDMASTER","CHALLENGER"]
    DIV_ORDER  = ["IV", "III", "II", "I"]

    def rank_score(tier, div):
        t = TIER_ORDER.index(tier) if tier in TIER_ORDER else -1
        d = DIV_ORDER.index(div)   if div  in DIV_ORDER  else 0
        return t * 4 + d

    old_score = rank_score(old["tier"], old["division"])
    new_score = rank_score(new_tier, new_div)
    promoted  = new_score > old_score
    demoted   = new_score < old_score

    user["rank"] = {"tier": new_tier, "division": new_div, "lp": new_lp}

    if promoted:
        user["gold"] = max(0, user["gold"] + RANK_UP_BONUS)
        return {"promoted": True, "tier": new_tier, "div": new_div, "bonus": RANK_UP_BONUS}
    if demoted:
        user["gold"] = max(0, user["gold"] + RANK_DOWN_PENALTY)
        return {"demoted": True, "tier": new_tier, "div": new_div, "penalty": RANK_DOWN_PENALTY}
    return None

def compute_power(user: dict) -> int:
    from bot.config import TERRITORY_GOLD_VALUE
    return user["gold"] + user["territory"] * TERRITORY_GOLD_VALUE

def award_shame_title(user: dict) -> str:
    """Assign a shame title with a 24-hour expiry."""
    import time
    from bot.config import SHAME_DURATION
    title = random.choice(SHAME_TITLES)
    user["shame"] = {"title": title, "expires_at": time.time() + SHAME_DURATION}
    user["stats"]["joust_losses"] += 1
    return title

def is_shamed(user: dict) -> str | None:
    """Return the active shame title if still valid, else clear and return None."""
    import time
    shame = user.get("shame")
    if not shame:
        return None
    if time.time() > shame["expires_at"]:
        user["shame"] = None
        return None
    return shame["title"]

def clear_shame(user: dict) -> str | None:
    """Remove shame on joust win. Returns cleared title or None."""
    shame = user.get("shame")
    cleared = shame["title"] if shame else None
    user["shame"] = None
    user["stats"]["joust_wins"] += 1
    return cleared

def award_glory_title(user: dict) -> str:
    title = random.choice(GLORY_TITLES)
    if title not in user["titles"]:
        user["titles"].append(title)
    return title