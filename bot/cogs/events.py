# ─────────────────────────────────────────────
#  The Summoner's Court  ·  cogs/events.py
# ─────────────────────────────────────────────

import asyncio
import time
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone

import bot.state      as state
import bot.storage    as storage
import bot.narration  as narration
import bot.kingdom    as kingdom
import bot.helpers    as helpers
import bot.riot_api   as riot
from bot.presence     import is_in_lol_game
from bot.config       import (
    MATCH_FETCH_DELAY, WEEKLY_RECAP_DAY, WEEKLY_RECAP_HOUR,
    DAILY_STIPEND, DAILY_STIPEND_CAP,
)

VOICE_REQUIRED_SECONDS = 30 * 60  # 30 minutes in voice to earn stipend


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot       = bot
        self.weekly_log: list[str] = []
        self.weekly_recap_task.start()

    def cog_unload(self):
        self.weekly_recap_task.cancel()

    # ── Presence tracking ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        uid = str(after.id)
        if uid not in state.user_data or not state.user_data[uid].get("riot_id"):
            return

        was_in_game = uid in state.active_games
        now_in_game = is_in_lol_game(after)

        if not was_in_game and now_in_game:
            state.active_games[uid] = time.time()
        elif was_in_game and not now_in_game:
            del state.active_games[uid]
            self.bot.loop.create_task(self._fetch_match_after_delay(after))

    # ── Match result pipeline ────────────────────────────────────────────

    async def _fetch_match_after_delay(self, member: discord.Member):
        await asyncio.sleep(MATCH_FETCH_DELAY)
        uid  = str(member.id)
        user = state.user_data.get(uid)
        if not user or not user.get("puuid"):
            return

        match_ids = await riot.get_recent_match_ids(user["puuid"], user["region"], count=1)
        if not match_ids:
            return
        match_id = match_ids[0]
        if match_id == user.get("last_match_id"):
            return

        match = await riot.get_match(match_id, user["region"])
        if not match:
            return
        participant = riot.extract_participant(match, user["puuid"])
        if not participant:
            return

        user["last_match_id"] = match_id
        game_duration         = match["info"].get("gameDuration", 9999)
        champ                 = participant.get("championName", "Unknown")

        # ── Lord's own result ─────────────────────────────────────────────
        match_delta = kingdom.apply_match_result(user, participant, game_duration)
        new_rank    = await riot.get_rank(user["puuid"], user["region"])
        rank_change = kingdom.apply_rank_change(user, new_rank)

        # ── Narration ─────────────────────────────────────────────────────
        kda_str = riot.format_kda(participant)
        if match_delta["won"]:
            narr = await narration.narrate_win(user["house"]["name"], champ, kda_str, participant.get("kills", 0))
        else:
            early_ff = game_duration < 20 * 60
            narr = await narration.narrate_loss(user["house"]["name"], champ, kda_str, early_ff)
        if match_delta.get("penta"):
            narr += "\n\n" + await narration.narrate_penta(user["house"]["name"], champ)

        # ── Backers: passive share + wager resolution ─────────────────────
        backer_lines = []
        for bid, backer in state.user_data.items():
            if backer.get("backing") != uid:
                continue

            # Passive cut
            b_result = kingdom.apply_backing_result(backer, match_delta["won"], match_delta.get("penta", False))
            sign     = "+" if b_result["delta"] >= 0 else ""
            backer_lines.append(
                f"{backer['house']['sigil']} **{backer['house']['name']}**  "
                f"{sign}{b_result['delta']} 🪙 → {backer['gold']:,} 🪙"
            )

            # Wager resolution
            w_result = kingdom.resolve_wager(backer, match_delta["won"])
            if w_result:
                if w_result["correct"]:
                    backer_lines.append(
                        f"  🎲 Wager WIN — called **{'WIN' if w_result['outcome']=='win' else 'LOSS'}** "
                        f"+{w_result['amount'] * 2} 🪙"
                    )
                else:
                    backer_lines.append(
                        f"  🎲 Wager LOSS — called **{'WIN' if w_result['outcome']=='win' else 'LOSS'}** "
                        f"-{w_result['amount']} 🪙"
                    )

        # ── Persist ───────────────────────────────────────────────────────
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)

        # ── Weekly log ───────────────────────────────────────────────────
        kda_p = participant
        result_word = "won" if match_delta["won"] else "lost"
        self.weekly_log.append(
            f"{user['house']['name']} {result_word} on {champ} "
            f"({kda_p.get('kills',0)}/{kda_p.get('deaths',0)}/{kda_p.get('assists',0)})"
        )
        if match_delta.get("penta"):
            self.weekly_log.append(f"{user['house']['name']} got a PENTAKILL on {champ}!")

        # ── Build and send embed ──────────────────────────────────────────
        embed = helpers.result_embed(member, user, participant, match_delta, rank_change, narr)
        if backer_lines:
            embed.add_field(name="🛡️ Allied Houses", value="\n".join(backer_lines), inline=False)
        await self._broadcast(embed)

        # Rank change narration + shame bell
        if rank_change:
            if rank_change.get("promoted"):
                rank_narr = await narration.narrate_rank_up(user["house"]["name"], rank_change["tier"], rank_change["div"])
                self.weekly_log.append(f"{user['house']['name']} promoted to {rank_change['tier']} {rank_change['div']}!")
            else:
                rank_narr = await narration.narrate_rank_down(user["house"]["name"], rank_change["tier"], rank_change["div"])
                self.weekly_log.append(f"{user['house']['name']} DEMOTED to {rank_change['tier']} {rank_change['div']}.")

            extra = discord.Embed(
                description=f"*{rank_narr}*",
                color=0xF1C40F if rank_change.get("promoted") else 0x7F8C8D,
            )
            await self._broadcast(extra)

            if rank_change.get("demoted"):
                shame_embed = discord.Embed(
                    title="🔔  THE SHAME BELL TOLLS",
                    description=f"**{user['house']['name']}** has fallen.\n*{rank_narr}*",
                    color=0x2C3E50,
                )
                await self._broadcast_shame(shame_embed)

    # ── Weekly Recap ─────────────────────────────────────────────────────

    @tasks.loop(minutes=30)
    async def weekly_recap_task(self):
        now = datetime.now(timezone.utc)
        if now.weekday() != WEEKLY_RECAP_DAY or now.hour != WEEKLY_RECAP_HOUR:
            return
        if not self.weekly_log:
            return
        for guild in self.bot.guilds:
            recap = await narration.weekly_recap(self.weekly_log, guild.name)
            embed = discord.Embed(
                title="📜  The Kingdom Chronicle — Weekly Decree",
                description=recap,
                color=0xF39C12,
            )
            ch_id = state.announcement_channels.get(str(guild.id))
            if ch_id:
                ch = guild.get_channel(ch_id)
                if ch:
                    await ch.send(embed=embed)
        self.weekly_log.clear()

    @weekly_recap_task.before_loop
    async def before_weekly_recap(self):
        await self.bot.wait_until_ready()

    # ── Voice Activity Stipend ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        uid   = str(member.id)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Reset accumulated time if it's a new day
        if state.voice_daily_claimed.get(uid) != today and uid in state.voice_accumulated:
            # New day but hasn't claimed yet — keep accumulation
            pass

        was_in_voice = before.channel is not None
        now_in_voice = after.channel is not None

        # Joined voice
        if not was_in_voice and now_in_voice:
            state.voice_joined_at[uid] = time.time()
            # Reset accumulation on new day
            if state.voice_daily_claimed.get(uid, "") < today:
                state.voice_accumulated.pop(uid, None)
            return

        # Left voice (or moved channels — still in voice, so skip)
        if was_in_voice and not now_in_voice:
            joined = state.voice_joined_at.pop(uid, None)
            if joined is None:
                return

            # Already claimed today — don't bother tracking
            if state.voice_daily_claimed.get(uid) == today:
                return

            # Not registered — don't track
            if uid not in state.user_data:
                return

            # Accumulate session time
            session = time.time() - joined
            accumulated = state.voice_accumulated.get(uid, 0.0) + session
            state.voice_accumulated[uid] = accumulated

            # Check if they hit 30 minutes
            if accumulated >= VOICE_REQUIRED_SECONDS:
                user = state.user_data[uid]
                if user["gold"] < DAILY_STIPEND_CAP:
                    grant = min(DAILY_STIPEND, DAILY_STIPEND_CAP - user["gold"])
                    user["gold"] += grant
                    state.voice_daily_claimed[uid] = today
                    storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
                    print(f"[Stipend] {user['house']['name']} earned {grant} gold (voice activity)", flush=True)
                else:
                    state.voice_daily_claimed[uid] = today  # mark as done even if above cap

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _broadcast(self, embed: discord.Embed):
        for guild in self.bot.guilds:
            ch_id = state.announcement_channels.get(str(guild.id))
            if ch_id:
                ch = guild.get_channel(ch_id)
                if ch:
                    await ch.send(embed=embed)

    async def _broadcast_shame(self, embed: discord.Embed):
        for guild in self.bot.guilds:
            ch_id = state.shame_channels.get(str(guild.id)) or state.announcement_channels.get(str(guild.id))
            if ch_id:
                ch = guild.get_channel(ch_id)
                if ch:
                    await ch.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))