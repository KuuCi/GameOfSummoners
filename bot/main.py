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

        for cog in COGS:
            await bot.load_extension(cog)

        synced = await bot.tree.sync()
        print(f"[Court] Logged in as {bot.user} | {len(synced)} commands synced")
        print(f"[Court] {len(state.user_data)} houses loaded from storage")

    @bot.event
    async def on_guild_join(guild: discord.Guild):
        print(f"[Court] Joined guild: {guild.name} ({guild.id})")

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN is not set.")

    await bot.start(token)