# ─────────────────────────────────────────────
#  The Summoner's Court  ·  riot_api.py
# ─────────────────────────────────────────────

import os
import asyncio
import aiohttp
from typing import Optional
from bot.config import ROUTING

API_KEY = os.getenv("RIOT_API_KEY", "")
TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5, sock_read=8)

def _headers() -> dict:
    return {"X-Riot-Token": API_KEY}

def _route(region: str) -> str:
    return ROUTING.get(region.lower(), "americas")

# ── Champion ID → Name (loaded once on startup) ───────────────────────────
_champ_map: dict[int, str] = {}

async def load_champion_map() -> None:
    global _champ_map
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get("https://ddragon.leagueoflegends.com/api/versions.json") as r:
                versions = await r.json(content_type=None)
                latest   = versions[0]
            async with s.get(f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json") as r:
                data = await r.json(content_type=None)
                _champ_map = {int(v["key"]): v["name"] for v in data["data"].values()}
        print(f"[Riot] Loaded {len(_champ_map)} champions from Data Dragon")
    except Exception as e:
        print(f"[Riot] Failed to load champion map: {e}")

def champion_name(champ_id: int) -> str:
    return _champ_map.get(champ_id, f"Champ#{champ_id}")

# ── Core API calls ────────────────────────────────────────────────────────

async def get_account_by_riot_id(game_name: str, tag_line: str, region: str) -> Optional[dict]:
    routing = _route(region)
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    print(f"[Riot] GET account {game_name}#{tag_line} ({routing})")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Account status: {r.status}")
                return await r.json() if r.status == 200 else None
    except Exception as e:
        print(f"[Riot] Account error: {e}"); return None

async def get_summoner_by_puuid(puuid: str, region: str) -> Optional[dict]:
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    print(f"[Riot] GET summoner ({region})")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Summoner status: {r.status}")
                return await r.json() if r.status == 200 else None
    except Exception as e:
        print(f"[Riot] Summoner error: {e}"); return None

async def get_rank(summoner_id: str, region: str) -> Optional[dict]:
    url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    print(f"[Riot] GET rank ({region})")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Rank status: {r.status}")
                if r.status != 200:
                    return None
                entries = await asyncio.wait_for(r.json(), timeout=8)
                for e in entries:
                    if e.get("queueType") == "RANKED_SOLO_5x5":
                        return e
                print(f"[Riot] No solo queue rank found")
                return None
    except asyncio.TimeoutError:
        print(f"[Riot] Rank timed out — returning None"); return None
    except Exception as e:
        print(f"[Riot] Rank error: {e}"); return None

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
                return await r.json() if r.status == 200 else []
    except Exception as e:
        print(f"[Riot] Match ids error: {e}"); return []

async def get_match(match_id: str, region: str) -> Optional[dict]:
    routing = _route(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    print(f"[Riot] GET match {match_id}")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Match status: {r.status}")
                return await r.json() if r.status == 200 else None
    except Exception as e:
        print(f"[Riot] Match error: {e}"); return None

async def get_live_game(summoner_id: str, region: str) -> Optional[dict]:
    url = f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{summoner_id}"
    print(f"[Riot] GET live game ({region})")
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                print(f"[Riot] Live game status: {r.status}")
                return await r.json() if r.status == 200 else None
    except Exception as e:
        print(f"[Riot] Live game error: {e}"); return None

async def get_account_by_puuid(puuid: str, region: str) -> Optional[dict]:
    routing = _route(region)
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}"
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(url, headers=_headers()) as r:
                return await r.json() if r.status == 200 else None
    except Exception as e:
        print(f"[Riot] Account by puuid error: {e}"); return None

# ── Participant analysis ──────────────────────────────────────────────────

async def analyze_participant(puuid: str, champ_id: int, region: str) -> dict:
    """
    Fetch recent ranked games for a live game participant and return annotations:
      streak:      "W3" / "L4" / None  (3+ consecutive)
      first_timer: True if 0 games on this champ in last 20 ranked
      smurf_flag:  True if <20 ranked games but >65% winrate
      winrate:     float | None
      games:       int
    """
    routing = _route(region)

    # Fetch last 20 ranked match IDs
    ids_url = (
        f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?queue=420&type=ranked&count=20"
    )
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(ids_url, headers=_headers()) as r:
                match_ids = await r.json() if r.status == 200 else []
    except Exception:
        match_ids = []

    if not match_ids:
        return {"streak": None, "first_timer": None, "smurf_flag": False, "winrate": None, "games": 0}

    # Fetch up to 10 matches in parallel
    async def _fetch_match(mid: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
                async with s.get(
                    f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{mid}",
                    headers=_headers()
                ) as r:
                    return await r.json() if r.status == 200 else None
        except Exception:
            return None

    matches = await asyncio.gather(*[_fetch_match(mid) for mid in match_ids[:10]])
    matches = [m for m in matches if m]

    wins        = 0
    results     = []
    champ_games = 0

    for m in matches:
        for p in m.get("info", {}).get("participants", []):
            if p.get("puuid") == puuid:
                won = p.get("win", False)
                results.append(won)
                wins += 1 if won else 0
                if p.get("championId") == champ_id:
                    champ_games += 1
                break

    total   = len(results)
    winrate = wins / total if total else None

    # Streak: 3+ consecutive same result from newest
    streak = None
    if results:
        kind, count = results[0], 1
        for res in results[1:]:
            if res == kind:
                count += 1
            else:
                break
        if count >= 3:
            streak = f"{'W' if kind else 'L'}{count}"

    first_timer = champ_games == 0 and total >= 5
    smurf_flag  = total < 20 and winrate is not None and winrate > 0.65

    return {
        "streak":      streak,
        "first_timer": first_timer,
        "smurf_flag":  smurf_flag,
        "winrate":     winrate,
        "games":       total,
    }

# ── Helpers ───────────────────────────────────────────────────────────────

def extract_participant(match: dict, puuid: str) -> Optional[dict]:
    for p in match.get("info", {}).get("participants", []):
        if p.get("puuid") == puuid:
            return p
    return None

def format_kda(p: dict) -> str:
    k, d, a = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
    ratio = (k + a) / max(d, 1)
    return f"{k}/{d}/{a} ({ratio:.2f} KDA)"

async def get_recent_streak(puuid: str, region: str, count: int = 5) -> dict:
    """
    Returns streak info for the war effort embed.
    { type: 'win'|'loss'|None, streak: int, record: str }
    """
    routing = _route(region)
    ids_url = (
        f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?queue=420&type=ranked&count={count}"
    )
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(ids_url, headers=_headers()) as r:
                match_ids = await r.json() if r.status == 200 else []
    except Exception:
        match_ids = []
 
    if not match_ids:
        return {"type": None, "streak": 0, "record": ""}
 
    async def _fetch(mid):
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
                async with s.get(
                    f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{mid}",
                    headers=_headers()
                ) as r:
                    return await r.json() if r.status == 200 else None
        except Exception:
            return None
 
    matches = await asyncio.gather(*[_fetch(mid) for mid in match_ids])
    results = []
    for m in matches:
        if not m:
            continue
        for p in m.get("info", {}).get("participants", []):
            if p.get("puuid") == puuid:
                results.append(p.get("win", False))
                break
 
    if not results:
        return {"type": None, "streak": 0, "record": ""}
 
    wins   = sum(results)
    losses = len(results) - wins
    record = f"{wins}W {losses}L last {len(results)}"
 
    kind, streak = results[0], 1
    for r in results[1:]:
        if r == kind:
            streak += 1
        else:
            break
 
    return {"type": "win" if kind else "loss", "streak": streak, "record": record}