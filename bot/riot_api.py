# ─────────────────────────────────────────────
#  The Summoner's Court  ·  riot_api.py
# ─────────────────────────────────────────────

import os
import aiohttp
from typing import Optional
from bot.config import ROUTING

API_KEY = os.getenv("RIOT_API_KEY", "")
TIMEOUT = aiohttp.ClientTimeout(total=10)

# Cache for champion ID → name mapping from Data Dragon
_champion_id_to_name: dict[int, str] = {}

async def _ensure_champion_map() -> None:
    """Fetch champion data from Data Dragon once and cache it."""
    if _champion_id_to_name:
        return
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get("https://ddragon.leagueoflegends.com/api/versions.json") as r:
                if r.status != 200:
                    return
                versions = await r.json()
            version = versions[0]
            async with s.get(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json") as r:
                if r.status != 200:
                    return
                data = await r.json()
            for name, info in data.get("data", {}).items():
                _champion_id_to_name[int(info["key"])] = name
        print(f"[Riot] Loaded {len(_champion_id_to_name)} champions from Data Dragon v{version}", flush=True)
    except Exception as e:
        print(f"[Riot] Data Dragon error: {e}", flush=True)

def champion_name_by_id(champion_id: int) -> Optional[str]:
    return _champion_id_to_name.get(champion_id)

def _headers() -> dict:
    return {"X-Riot-Token": API_KEY}

def _route(region: str) -> str:
    return ROUTING.get(region.lower(), "americas")

async def get_account_by_riot_id(game_name: str, tag_line: str, region: str) -> Optional[dict]:
    routing = _route(region)
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    print(f"[Riot] GET account {game_name}#{tag_line} ({routing})", flush=True)
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Account status: {r.status}", flush=True)
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[Riot] Account error: {e}", flush=True)
        return None

async def get_summoner_by_puuid(puuid: str, region: str) -> Optional[dict]:
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    print(f"[Riot] GET summoner by puuid ({region})", flush=True)
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Summoner status: {r.status}", flush=True)
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[Riot] Summoner error: {e}", flush=True)
        return None

async def get_rank(puuid: str, region: str) -> Optional[dict]:
    url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    print(f"[Riot] GET rank by puuid ({region})", flush=True)
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Rank status: {r.status}", flush=True)
                if r.status != 200:
                    return None
                entries = await r.json()
                for e in entries:
                    if e.get("queueType") == "RANKED_SOLO_5x5":
                        return e
                return None
    except Exception as e:
        print(f"[Riot] Rank error: {e}", flush=True)
        return None

async def get_top_mastery(puuid: str, region: str, count: int = 3) -> list[dict]:
    url = f"https://{region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count={count}"
    print(f"[Riot] GET top mastery ({region})", flush=True)
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Mastery status: {r.status}", flush=True)
                if r.status != 200:
                    return []
                return await r.json()
    except Exception as e:
        print(f"[Riot] Mastery error: {e}", flush=True)
        return []

async def get_active_game(puuid: str, region: str) -> Optional[dict]:
    url = f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    print(f"[Riot] GET active game ({region})", flush=True)
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Active game status: {r.status}", flush=True)
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[Riot] Active game error: {e}", flush=True)
        return None

async def get_recent_streak(puuid: str, region: str, count: int = 5) -> dict:
    """Check the player's last N ranked games for win/loss streaks."""
    match_ids = await get_recent_match_ids(puuid, region, count=count)
    results = []
    for mid in match_ids:
        m = await get_match(mid, region)
        if not m:
            continue
        p = extract_participant(m, puuid)
        if p:
            results.append(p.get("win", False))

    if not results:
        return {"streak": 0, "type": "none", "record": ""}

    # Current streak
    streak_type = "win" if results[0] else "loss"
    streak = 0
    for r in results:
        if r == results[0]:
            streak += 1
        else:
            break

    wins   = sum(1 for r in results if r)
    losses = len(results) - wins
    return {
        "streak": streak,
        "type": streak_type,
        "record": f"{wins}W {losses}L last {len(results)}",
    }

async def get_recent_match_ids(puuid: str, region: str, count: int = 5) -> list[str]:
    routing = _route(region)
    url = (
        f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?queue=420&type=ranked&count={count}"
    )
    print(f"[Riot] GET match ids ({routing})", flush=True)
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Match ids status: {r.status}", flush=True)
                if r.status != 200:
                    return []
                return await r.json()
    except Exception as e:
        print(f"[Riot] Match ids error: {e}", flush=True)
        return []

async def get_match(match_id: str, region: str) -> Optional[dict]:
    routing = _route(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    print(f"[Riot] GET match {match_id}", flush=True)
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Match status: {r.status}", flush=True)
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[Riot] Match error: {e}", flush=True)
        return None

def extract_participant(match: dict, puuid: str) -> Optional[dict]:
    for p in match.get("info", {}).get("participants", []):
        if p.get("puuid") == puuid:
            return p
    return None

def format_kda(p: dict) -> str:
    k, d, a = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
    ratio = (k + a) / max(d, 1)
    return f"{k}/{d}/{a} ({ratio:.2f} KDA)"

async def get_champion_recent_stats(puuid: str, region: str, champion: str, scan_count: int = 15) -> dict:
    """Scan recent ranked games for stats on a specific champion."""
    match_ids = await get_recent_match_ids(puuid, region, count=scan_count)
    games = []
    for mid in match_ids:
        m = await get_match(mid, region)
        if not m:
            continue
        p = extract_participant(m, puuid)
        if not p:
            continue
        if p.get("championName", "").lower() == champion.lower():
            games.append({
                "win": p.get("win", False),
                "kills": p.get("kills", 0),
                "deaths": p.get("deaths", 0),
                "assists": p.get("assists", 0),
                "cs": p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
            })

    if not games:
        return {"found": 0}

    wins   = sum(1 for g in games if g["win"])
    losses = len(games) - wins
    avg_k  = sum(g["kills"] for g in games) / len(games)
    avg_d  = sum(g["deaths"] for g in games) / len(games)
    avg_a  = sum(g["assists"] for g in games) / len(games)
    avg_cs = sum(g["cs"] for g in games) / len(games)

    # Current streak on this champ
    streak = 0
    streak_type = "win" if games[0]["win"] else "loss"
    for g in games:
        if g["win"] == games[0]["win"]:
            streak += 1
        else:
            break

    return {
        "found": len(games),
        "wins": wins,
        "losses": losses,
        "avg_kda": f"{avg_k:.1f}/{avg_d:.1f}/{avg_a:.1f}",
        "avg_cs": f"{avg_cs:.0f}",
        "streak": streak,
        "streak_type": streak_type,
    }