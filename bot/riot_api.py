# ─────────────────────────────────────────────
#  The Summoner's Court  ·  riot_api.py
# ─────────────────────────────────────────────

import os
import aiohttp
from typing import Optional
from bot.config import ROUTING

API_KEY = os.getenv("RIOT_API_KEY", "")
TIMEOUT = aiohttp.ClientTimeout(total=10)

def _headers() -> dict:
    return {"X-Riot-Token": API_KEY}

def _route(region: str) -> str:
    return ROUTING.get(region.lower(), "americas")

async def get_account_by_riot_id(game_name: str, tag_line: str, region: str) -> Optional[dict]:
    routing = _route(region)
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    print(f"[Riot] GET account {game_name}#{tag_line} ({routing})")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Account status: {r.status}")
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[Riot] Account error: {e}")
        return None

async def get_summoner_by_puuid(puuid: str, region: str) -> Optional[dict]:
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    print(f"[Riot] GET summoner by puuid ({region})")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Summoner status: {r.status}")
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[Riot] Summoner error: {e}")
        return None

async def get_rank(summoner_id: str, region: str) -> Optional[dict]:
    url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    print(f"[Riot] GET rank ({region})")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Rank status: {r.status}")
                if r.status != 200:
                    return None
                entries = await r.json()
                for e in entries:
                    if e.get("queueType") == "RANKED_SOLO_5x5":
                        return e
                return None
    except Exception as e:
        print(f"[Riot] Rank error: {e}")
        return None

async def get_recent_match_ids(puuid: str, region: str, count: int = 5) -> list[str]:
    routing = _route(region)
    url = (
        f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?queue=420&type=ranked&count={count}"
    )
    print(f"[Riot] GET match ids ({routing})")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Match ids status: {r.status}")
                if r.status != 200:
                    return []
                return await r.json()
    except Exception as e:
        print(f"[Riot] Match ids error: {e}")
        return []

async def get_match(match_id: str, region: str) -> Optional[dict]:
    routing = _route(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    print(f"[Riot] GET match {match_id}")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Match status: {r.status}")
                if r.status != 200:
                    return None
                return await r.json()
    except Exception as e:
        print(f"[Riot] Match error: {e}")
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