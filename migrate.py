"""
migrate_summoner_id.py
─────────────────────
Run this once locally to backfill summoner_id for all users missing it.

Usage:
    RIOT_API_KEY=RGAPI-xxx python migrate_summoner_id.py

Point DATA_FILE at your kingdom.json — either download it from Railway
first, run the script, then re-upload it.
"""

import asyncio
import json
import os
import aiohttp

DATA_FILE = "data/kingdom.json"
API_KEY   = os.environ["RIOT_API_KEY"]
TIMEOUT   = aiohttp.ClientTimeout(total=10, connect=5, sock_read=8)

def headers():
    return {"X-Riot-Token": API_KEY}

async def get_summoner(puuid: str, region: str):
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
        async with s.get(url, headers=headers()) as r:
            data = await r.json()
            if r.status == 200 and "id" in data:
                return data
            print(f"  ✗ HTTP {r.status}: {data}")
            return None

async def main():
    with open(DATA_FILE) as f:
        data = json.load(f)

    users   = data.get("users", {})
    updated = 0

    for uid, user in users.items():
        house  = user.get("house", {}).get("name", uid)
        puuid  = user.get("puuid")
        region = user.get("region")

        if user.get("summoner_id"):
            print(f"  ✓ {house}: already has summoner_id")
            continue

        if not puuid or not region:
            print(f"  ? {house}: missing puuid or region, skipping")
            continue

        print(f"  → {house}: fetching summoner_id...", end=" ", flush=True)
        summoner = await get_summoner(puuid, region)
        if summoner:
            user["summoner_id"] = summoner["id"]
            updated += 1
            print(f"✓ {summoner['id'][:12]}...")
        else:
            print("✗ failed")

    if updated:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nDone. Updated {updated} user(s). Save {DATA_FILE} back to Railway.")
    else:
        print("\nNothing to update.")

asyncio.run(main())