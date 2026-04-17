# ─────────────────────────────────────────────
#  The Summoner's Court  ·  bot/main.py
# ─────────────────────────────────────────────

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import bot.state    as state
import bot.storage  as storage
import bot.riot_api as riot

load_dotenv()

COGS = [
    "bot.cogs.events",
    "bot.cogs.commands",
]

async def create_bot():
    intents = discord.Intents.default()
    intents.members         = True
    intents.presences       = True
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        storage.load_all_state(
            state.user_data,
            state.announcement_channels,
            state.shame_channels,
        )
        await riot.load_champion_map()

        # Migrate existing users missing summoner_id
        migrated = 0
        for uid, user in state.user_data.items():
            if not user.get("summoner_id") and user.get("puuid") and user.get("region"):
                summoner = await riot.get_summoner_by_puuid(user["puuid"], user["region"])
                if summoner:
                    user["summoner_id"] = summoner["id"]
                    migrated += 1
        if migrated:
            storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
            print(f"[Court] Migrated summoner_id for {migrated} user(s)", flush=True)

        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"[Court] Loaded {cog}", flush=True)
            except Exception as e:
                print(f"[Court] Failed to load {cog}: {e}", flush=True)
                import traceback
                traceback.print_exc()

        synced = await bot.tree.sync()
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
            print(f"[Court] Guild sync done for {guild.name}", flush=True)
        print(f"[Court] Logged in as {bot.user} | {len(synced)} commands synced")
        print(f"[Court] {len(state.user_data)} houses loaded from storage")

    @bot.event
    async def on_guild_join(guild: discord.Guild):
        print(f"[Court] Joined guild: {guild.name} ({guild.id})")

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN is not set.")

    await bot.start(token)