# ─────────────────────────────────────────────
#  The Summoner's Court  ·  helpers.py
# ─────────────────────────────────────────────

import discord
from typing import Optional
from bot.kingdom import compute_power

RANK_EMOJI = {
    "IRON":        "🔩",
    "BRONZE":      "🥉",
    "SILVER":      "🥈",
    "GOLD":        "🥇",
    "PLATINUM":    "💠",
    "EMERALD":     "💚",
    "DIAMOND":     "💎",
    "MASTER":      "👑",
    "GRANDMASTER": "👑👑",
    "CHALLENGER":  "🏆",
    "UNRANKED":    "❓",
}

def rank_str(rank: dict) -> str:
    tier = rank.get("tier", "UNRANKED")
    div  = rank.get("division", "")
    lp   = rank.get("lp", 0)
    emoji = RANK_EMOJI.get(tier, "❓")
    if tier in ("MASTER", "GRANDMASTER", "CHALLENGER"):
        return f"{emoji} {tier} {lp} LP"
    if div:
        return f"{emoji} {tier} {div} — {lp} LP"
    return f"{emoji} UNRANKED"

def house_embed(user: dict, discord_user: discord.User | discord.Member) -> discord.Embed:
    house  = user["house"]
    rank   = user["rank"]
    stats  = user["stats"]
    power  = compute_power(user)
    wins   = stats["wins"]
    losses = stats["losses"]
    wr     = f"{wins/(wins+losses)*100:.0f}%" if wins + losses else "N/A"

    embed = discord.Embed(
        title=f"{house['sigil']}  {house['name']}",
        description=f"*\"{house['motto']}\"*\n{house['flavor']}",
        color=house["color"],
    )
    embed.set_author(name=str(discord_user), icon_url=discord_user.display_avatar.url)
    embed.add_field(name="Rank",      value=rank_str(rank),                     inline=True)
    embed.add_field(name="Power",     value=f"⚡ {power:,}",                    inline=True)
    embed.add_field(name="Gold",      value=f"🪙 {user['gold']:,}",             inline=True)
    embed.add_field(name="Territory", value=f"🗺️ {user['territory']} tiles",    inline=True)
    embed.add_field(name="Record",    value=f"✅ {wins}W  ❌ {losses}L  ({wr})", inline=True)
    embed.add_field(name="Pentas",    value=f"💥 {stats['pentas']}",             inline=True)
    jw = stats.get("joust_wins", 0)
    jl = stats.get("joust_losses", 0)
    embed.add_field(name="Jousts",    value=f"🏇 {jw}W  {jl}L",                 inline=True)
    if user.get("shame"):
        import time
        remaining = int((user["shame"]["expires_at"] - time.time()) / 3600)
        if remaining > 0:
            embed.add_field(name="😔 Shame", value=f'"{user["shame"]["title"]}" — clears in ~{remaining}h or win a joust', inline=False)
        else:
            user["shame"] = None
        if user["titles"]:
        embed.add_field(name="Titles", value="\n".join(user["titles"]), inline=False)
    embed.set_footer(text=f"Riot ID: {user['riot_id']}  ·  Region: {user['region'].upper()}")
    return embed

def result_embed(
    discord_user: discord.User | discord.Member,
    user: dict,
    participant: dict,
    match_delta: dict,
    rank_change: Optional[dict],
    narration: str,
) -> discord.Embed:
    house = user["house"]
    won   = match_delta["won"]
    champ = participant.get("championName", "Unknown")
    kda   = f"{participant.get('kills',0)}/{participant.get('deaths',0)}/{participant.get('assists',0)}"
    cs    = participant.get("totalMinionsKilled", 0) + participant.get("neutralMinionsKilled", 0)

    color  = 0x2ECC71 if won else 0xE74C3C
    result = "⚔️  VICTORY" if won else "💀  DEFEAT"

    embed = discord.Embed(
        title=f"{house['sigil']}  {house['name']}  —  {result}",
        description=f"*{narration}*" if narration else "",
        color=color,
    )
    embed.set_author(name=str(discord_user), icon_url=discord_user.display_avatar.url)
    embed.add_field(name="Champion", value=champ, inline=True)
    embed.add_field(name="KDA",      value=kda,   inline=True)
    embed.add_field(name="CS",       value=str(cs), inline=True)

    reason_text = "\n".join(match_delta["reasons"])
    embed.add_field(name="Gold Changes", value=reason_text, inline=False)
    embed.add_field(name="Treasury",     value=f"🪙 {user['gold']:,}", inline=True)

    if rank_change:
        if rank_change.get("promoted"):
            embed.add_field(
                name="🎉 PROMOTION",
                value=f"Ascended to **{rank_change['tier']} {rank_change['div']}**  (+{rank_change['bonus']} 🪙)",
                inline=False,
            )
        elif rank_change.get("demoted"):
            embed.add_field(
                name="🔔 SHAME BELL",
                value=f"Fallen to **{rank_change['tier']} {rank_change['div']}**  ({rank_change['penalty']} 🪙)",
                inline=False,
            )
    return embed

def scout_embed(user: dict, discord_user: discord.User | discord.Member) -> discord.Embed:
    """Public kingdom intel — no private match history, just state data."""
    house  = user["house"]
    stats  = user["stats"]
    power  = compute_power(user)
    wins   = stats["wins"]
    losses = stats["losses"]
    wr     = f"{wins/(wins+losses)*100:.0f}%" if wins + losses else "N/A"

    embed = discord.Embed(
        title=f"🕵️  Intelligence Report: {house['sigil']} {house['name']}",
        color=0x2C3E50,
    )
    embed.set_author(name=str(discord_user), icon_url=discord_user.display_avatar.url)
    embed.add_field(name="Rank",      value=rank_str(user["rank"]),              inline=True)
    embed.add_field(name="Power",     value=f"⚡ {power:,}",                     inline=True)
    embed.add_field(name="Gold",      value=f"🪙 {user['gold']:,}",              inline=True)
    embed.add_field(name="Territory", value=f"🗺️ {user['territory']} tiles",     inline=True)
    embed.add_field(name="Record",    value=f"✅ {wins}W  ❌ {losses}L  ({wr})",  inline=True)
    embed.add_field(name="Pentas",    value=f"💥 {stats['pentas']}",              inline=True)
    embed.set_footer(text="This intelligence was gathered by your court's spies.")
    return embed

def backer_embed(backer: dict, discord_user: discord.User | discord.Member,
                 lord_name: str, lord_house_name: str) -> discord.Embed:
    w = backer["stats"]["backed_wins"]
    l = backer["stats"]["backed_losses"]
    wr = f"{w/(w+l)*100:.0f}%" if w + l else "N/A"
    embed = discord.Embed(
        title=f"🛡️  Vassal of {lord_house_name}",
        color=0x8E44AD,
    )
    embed.set_author(name=str(discord_user), icon_url=discord_user.display_avatar.url)
    embed.add_field(name="Lord",       value=lord_name,              inline=True)
    embed.add_field(name="Gold",       value=f"🪙 {backer['gold']:,}", inline=True)
    embed.add_field(name="Backed W/L", value=f"✅ {w}  ❌ {l}  ({wr})", inline=True)
    if backer["titles"]:
        embed.add_field(name="Titles", value="\n".join(backer["titles"]), inline=False)
    return embed

def leaderboard_embed(users: list[tuple[str, dict]], title: str = "⚡ Power Rankings") -> discord.Embed:
    embed = discord.Embed(title=title, color=0xF1C40F)
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, u) in enumerate(users[:10]):
        medal = medals[i] if i < 3 else f"**{i+1}.**"
        power = compute_power(u)
        lines.append(f"{medal} {u['house']['sigil']} **{u['house']['name']}** — ⚡ {power:,}  🪙 {u['gold']:,}")
    embed.description = "\n".join(lines) if lines else "*The kingdom is empty.*"
    return embed