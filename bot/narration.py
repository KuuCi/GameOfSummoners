# ─────────────────────────────────────────────
#  The Summoner's Court  ·  narration.py
# ─────────────────────────────────────────────
# All AI-generated flavour text lives here.
# We call the Anthropic API asynchronously.

import os
import asyncio
import aiohttp
import json
from bot.config import NARRATION_MODEL

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
API_URL = "https://api.anthropic.com/v1/messages"

async def _ask(system: str, user: str, max_tokens: int = 220) -> str:
    headers = {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": NARRATION_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(API_URL, headers=headers, json=body) as r:
            if r.status != 200:
                return ""
            data = await r.json()
            return data["content"][0]["text"].strip()

SYSTEM_HERALD = (
    "You are the trash-talking announcer for a League of Legends friend group Discord server. "
    "You speak like a medieval herald but with the energy of a group chat that roasts each other constantly. "
    "Be mean, specific, and funny. No corporate cringe, no safe softening, no emojis. "
    "These are friends, so go for the throat. Keep it under 3 sentences."
)

async def narrate_win(house_name: str, champion: str, kda: str, kills: int) -> str:
    prompt = (
        f"House '{house_name}' just won a ranked game on {champion} with a KDA of {kda}. "
        f"Announce their victory. You can hype them up but keep it grounded — one good game doesn't make them good."
    )
    return await _ask(SYSTEM_HERALD, prompt)

async def narrate_loss(house_name: str, champion: str, kda: str, early_ff: bool) -> str:
    ff_note = " They surrendered before 20 minutes like cowards." if early_ff else ""
    prompt = (
        f"House '{house_name}' just lost a ranked game on {champion} with a KDA of {kda}.{ff_note} "
        f"Roast them. Be specific and brutal. This is a friend group, go mean."
    )
    return await _ask(SYSTEM_HERALD, prompt)

async def narrate_penta(house_name: str, champion: str) -> str:
    prompt = (
        f"House '{house_name}' just got a pentakill on {champion}. "
        f"Announce it like it's the most impressive thing that's ever happened, while implying the enemies were probably bad."
    )
    return await _ask(SYSTEM_HERALD, prompt, max_tokens=180)

async def narrate_rank_up(house_name: str, new_tier: str, new_div: str) -> str:
    prompt = (
        f"House '{house_name}' just got promoted to {new_tier} {new_div}. "
        f"Announce the promotion. Acknowledge it while reminding everyone it took them this long."
    )
    return await _ask(SYSTEM_HERALD, prompt, max_tokens=150)

async def narrate_rank_down(house_name: str, new_tier: str, new_div: str) -> str:
    prompt = (
        f"House '{house_name}' just got DEMOTED to {new_tier} {new_div}. "
        f"Destroy them. This is a friend group roast, not a eulogy. Be mean and specific about what a demotion means."
    )
    return await _ask(SYSTEM_HERALD, prompt, max_tokens=150)

async def oracle_prediction(house_name: str, champion: str, recent_wins: int, recent_losses: int) -> str:
    record = f"{recent_wins}W {recent_losses}L recently"
    prompt = (
        f"House '{house_name}' is about to queue on {champion}. Their record is {record}. "
        f"Give a short prophecy about the game ahead. Can be ominous, can be hype, but make it feel earned based on the record. "
        f"2-3 sentences, herald voice."
    )
    return await _ask(SYSTEM_HERALD, prompt, max_tokens=180)

async def weekly_recap(events: list[str], server_name: str) -> str:
    events_text = "\n".join(f"- {e}" for e in events[:20])
    prompt = (
        f"Here are this week's League games in the '{server_name}' Discord:\n{events_text}\n\n"
        f"Write a weekly recap as a medieval herald for a friend group server. "
        f"3-4 sentences max. Name specific houses. Call out the worst performer and the best. "
        f"Keep it punchy — this gets posted in chat, not read at a ceremony."
    )
    return await _ask(SYSTEM_HERALD, prompt, max_tokens=300)

async def narrate_duel_result(winner_house: str, loser_house: str, wager: int) -> str:
    prompt = (
        f"House '{winner_house}' just beat House '{loser_house}' in a duel and took {wager} gold. "
        f"Announce it. Mock the loser specifically — losing a duel is embarrassing."
    )
    return await _ask(SYSTEM_HERALD, prompt, max_tokens=150)