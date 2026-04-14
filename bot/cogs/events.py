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
    WAR_EFFORT_MIN, WAR_EFFORT_MAX, WAR_EFFORT_WINDOW,
)

VOICE_REQUIRED_SECONDS = 30 * 60  # 30 minutes in voice to earn stipend


# ── War Effort Modal + Buttons ──────────────────────────────────────────

class WarEffortModal(discord.ui.Modal):
    """Pop-up that asks how much gold to stake."""

    amount_input = discord.ui.TextInput(
        label="Gold to stake",
        placeholder=f"{WAR_EFFORT_MIN}–{WAR_EFFORT_MAX}",
        min_length=1,
        max_length=5,
    )

    def __init__(self, player_uid: str, side: str):
        title = "Join the War Effort" if side == "support" else "Lodge a Protest"
        super().__init__(title=title)
        self.player_uid = player_uid
        self.side = side

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)

        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message("Enter a number.", ephemeral=True)
            return

        if not (WAR_EFFORT_MIN <= amount <= WAR_EFFORT_MAX):
            await interaction.response.send_message(
                f"Must be between {WAR_EFFORT_MIN} and {WAR_EFFORT_MAX} gold.", ephemeral=True
            )
            return

        if state.user_data[uid]["gold"] < amount:
            await interaction.response.send_message("Not enough gold.", ephemeral=True)
            return

        # Double-check they haven't pledged while the modal was open
        war = state.active_wars.get(self.player_uid)
        if not war:
            await interaction.response.send_message("This war effort has ended.", ephemeral=True)
            return
        if uid in war["supporters"] or uid in war["protesters"]:
            await interaction.response.send_message("You have already pledged.", ephemeral=True)
            return

        war[f"{self.side}s"][uid] = amount  # "supporters" or "protesters"
        house = state.user_data[uid]["house"]
        player_house = state.user_data[self.player_uid]["house"]
        action = "rallies behind" if self.side == "support" else "protests"

        sup_total = sum(war["supporters"].values())
        pro_total = sum(war["protesters"].values())
        await interaction.response.send_message(
            f"{house['sigil']} **{house['name']}** {action} **{player_house['name']}**! "
            f"({amount} 🪙 staked)\n"
            f"⚔️ {sup_total} 🪙 supporting · 🏳️ {pro_total} 🪙 protesting"
        )


class WarEffortView(discord.ui.View):
    """Buttons for supporting or protesting a lord's ranked game."""

    def __init__(self, player_uid: str):
        super().__init__(timeout=WAR_EFFORT_WINDOW)
        self.player_uid = player_uid

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    def _pre_check(self, uid: str) -> str | None:
        if uid not in state.user_data:
            return "You must `/register` first."
        if uid == self.player_uid:
            return "You cannot bet on your own game."
        if state.user_data[uid]["gold"] < WAR_EFFORT_MIN:
            return f"You need at least {WAR_EFFORT_MIN} gold."
        war = state.active_wars.get(self.player_uid, {})
        if uid in war.get("supporters", {}) or uid in war.get("protesters", {}):
            return "You have already pledged."
        return None

    @discord.ui.button(label="⚔️ Join War Effort", style=discord.ButtonStyle.green)
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._pre_check(str(interaction.user.id))
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_modal(WarEffortModal(self.player_uid, "supporter"))

    @discord.ui.button(label="🏳️ Protest", style=discord.ButtonStyle.red)
    async def protest(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._pre_check(str(interaction.user.id))
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_modal(WarEffortModal(self.player_uid, "protester"))


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
            # Post war effort call to arms
            await self._post_war_effort(after, uid)
        elif was_in_game and not now_in_game:
            del state.active_games[uid]
            self.bot.loop.create_task(self._fetch_match_after_delay(after))

    # ── War Effort broadcast ───────────────────────────────────────────

    async def _post_war_effort(self, member: discord.Member, uid: str):
        user  = state.user_data[uid]
        house = user["house"]
        state.active_wars[uid] = {"supporters": {}, "protesters": {}}

        embed = discord.Embed(
            title=f"📯  {house['sigil']} {house['name']} rides to war!",
            description=(
                f"**{member.display_name}** has entered a ranked game.\n\n"
                f"⚔️ **Join War Effort** — stake gold that they will conquer\n"
                f"🏳️ **Protest** — stake gold that they will fall\n\n"
                f"Pledge {WAR_EFFORT_MIN}–{WAR_EFFORT_MAX} 🪙 · *{WAR_EFFORT_WINDOW // 60} minutes to decide.*"
            ),
            color=house["color"],
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)

        view = WarEffortView(uid)
        for guild in self.bot.guilds:
            ch_id = state.announcement_channels.get(str(guild.id))
            if ch_id:
                ch = guild.get_channel(ch_id)
                if ch:
                    await ch.send(embed=embed, view=view)

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

        # ── War Effort resolution ───────────────────────────────────────────
        war_lines = []
        war = state.active_wars.pop(uid, None)
        if war:
            won = match_delta["won"]
            # Supporters win if player won, protesters win if player lost
            for sid, amount in war.get("supporters", {}).items():
                s = state.user_data.get(sid)
                if not s:
                    continue
                if won:
                    s["gold"] += amount
                    war_lines.append(f"⚔️ {s['house']['sigil']} **{s['house']['name']}**  +{amount} 🪙 ✅")
                else:
                    s["gold"] = max(0, s["gold"] - amount)
                    war_lines.append(f"⚔️ {s['house']['sigil']} **{s['house']['name']}**  -{amount} 🪙 ❌")

            for pid, amount in war.get("protesters", {}).items():
                p = state.user_data.get(pid)
                if not p:
                    continue
                if not won:
                    p["gold"] += amount
                    war_lines.append(f"🏳️ {p['house']['sigil']} **{p['house']['name']}**  +{amount} 🪙 ✅")
                else:
                    p["gold"] = max(0, p["gold"] - amount)
                    war_lines.append(f"🏳️ {p['house']['sigil']} **{p['house']['name']}**  -{amount} 🪙 ❌")

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
        if war_lines:
            embed.add_field(name="📯 War Effort", value="\n".join(war_lines), inline=False)
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