# ─────────────────────────────────────────────
#  The Summoner's Court  ·  cogs/commands.py
# ─────────────────────────────────────────────

import time
import random
import discord
from discord import app_commands
from discord.ext import commands

import bot.state     as state
import bot.storage   as storage
import bot.narration as narration
import bot.kingdom   as kingdom
import bot.helpers   as helpers
import bot.riot_api  as riot
from bot.config import (
    DUEL_WAGER_MIN, DUEL_WAGER_MAX, DUEL_EXPIRY, DEFAULT_REGION,
    BACKER_WAGER_MIN, BACKER_WAGER_MAX, BACKER_WIN_SHARE, BACKER_LOSS_SHARE,
)


class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /register ────────────────────────────────────────────────────────

    @app_commands.command(name="register", description="Forge your house and join the Summoner's Court.")
    @app_commands.describe(
        game_name="Your Riot ID name (e.g. Faker).",
        tag_line="Your Riot ID tag (e.g. NA1).",
        region="Your region (na1, euw1, kr…).",
    )
    async def register(self, interaction: discord.Interaction, game_name: str, tag_line: str, region: str = DEFAULT_REGION):
        await interaction.response.defer(thinking=True)
        uid = str(interaction.user.id)
        print(f"[Register] {interaction.user} → {game_name}#{tag_line} {region}", flush=True)

        try:
            account = await riot.get_account_by_riot_id(game_name, tag_line, region)
            if not account:
                print(f"[Register] Failed: account not found", flush=True)
                await interaction.followup.send("Could not find that Riot ID. Check the name, tag, and region.")
                return

            puuid = account["puuid"]
            print(f"[Register] Got puuid: {puuid[:8]}...", flush=True)

            rank_raw = await riot.get_rank(puuid, region)
            print(f"[Register] Rank fetched: {rank_raw.get('tier') if rank_raw else 'Unranked'}", flush=True)

            print(f"[Register] Fetching match history...", flush=True)
            match_ids = await riot.get_recent_match_ids(puuid, region, count=5)
            print(f"[Register] Got {len(match_ids)} match ids", flush=True)

            champ_pool = []
            for mid in match_ids[:3]:
                m = await riot.get_match(mid, region)
                if m:
                    p = riot.extract_participant(m, puuid)
                    if p:
                        champ = p.get("championName", "")
                        if champ and champ not in champ_pool:
                            champ_pool.append(champ)
            print(f"[Register] Champ pool: {champ_pool}", flush=True)

            house   = kingdom.generate_house(champ_pool)
            riot_id = f"{game_name}#{tag_line}"
            entry   = kingdom.new_user_entry(riot_id, puuid, region.lower(), house, rank_raw)

            state.user_data[uid] = entry
            storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
            print(f"[Register] Done — {house['name']} created for {interaction.user}", flush=True)

            embed = helpers.house_embed(entry, interaction.user)
            embed.set_footer(text=f"Welcome to the kingdom, {house['name']}. May your lanes never feed.")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Register] ERROR: {e}", flush=True)
            try:
                await interaction.followup.send(f"Something went wrong during registration: `{e}`")
            except Exception:
                pass

    # ── /unregister ──────────────────────────────────────────────────────

    @app_commands.command(name="unregister", description="Dissolve your house and leave the kingdom.")
    async def unregister(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid not in state.user_data:
            await interaction.response.send_message("You are not registered.", ephemeral=True)
            return
        house_name = state.user_data[uid]["house"]["name"]
        del state.user_data[uid]
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
        print(f"[Unregister] {interaction.user} dissolved {house_name}")
        await interaction.response.send_message(
            f"*{house_name} has been struck from the chronicles. Their banners burn.*", ephemeral=True
        )

    # ── /house ───────────────────────────────────────────────────────────

    @app_commands.command(name="house", description="View your house or another lord's house.")
    @app_commands.describe(member="Leave blank to view your own house.")
    async def house(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        uid    = str(target.id)
        if uid not in state.user_data:
            await interaction.response.send_message(f"{target.display_name} has not pledged their house yet.", ephemeral=True)
            return
        embed = helpers.house_embed(state.user_data[uid], target)
        await interaction.response.send_message(embed=embed)

    # ── /scout ────────────────────────────────────────────────────────────

    @app_commands.command(name="scout", description="View a lord's public kingdom standing.")
    @app_commands.describe(member="The lord to scout.")
    async def scout(self, interaction: discord.Interaction, member: discord.Member):
        uid = str(member.id)
        if uid not in state.user_data:
            await interaction.response.send_message(f"{member.display_name} has no house.", ephemeral=True)
            return
        embed = helpers.scout_embed(state.user_data[uid], member)
        await interaction.response.send_message(embed=embed)

    # ── /leaderboard ─────────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="The Power Rankings of the realm.")
    async def leaderboard(self, interaction: discord.Interaction):
        if not state.user_data:
            await interaction.response.send_message("The kingdom is empty.", ephemeral=True)
            return
        sorted_users = sorted(state.user_data.items(), key=lambda x: kingdom.compute_power(x[1]), reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, (uid, u) in enumerate(sorted_users[:12]):
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            h     = u["house"]
            tag   = f" *(backing <@{u['backing']}>)*" if u.get("backing") else ""
            lines.append(f"{medal} {h['sigil']} **{h['name']}** — ⚡ {kingdom.compute_power(u):,}  🪙 {u['gold']:,}{tag}")
        embed = discord.Embed(title="⚡ Power Rankings", color=0xF1C40F)
        embed.description = "\n".join(lines) if lines else "*The kingdom is empty.*"
        await interaction.response.send_message(embed=embed)

    # ── /oracle ───────────────────────────────────────────────────────────

    @app_commands.command(name="oracle", description="Consult the Oracle before your next game.")
    @app_commands.describe(champion="The champion you are about to play.")
    async def oracle(self, interaction: discord.Interaction, champion: str):
        uid = str(interaction.user.id)
        if uid not in state.user_data:
            await interaction.response.send_message("You must register first.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        user  = state.user_data[uid]
        text  = await narration.oracle_prediction(user["house"]["name"], champion, user["stats"]["wins"], user["stats"]["losses"])
        embed = discord.Embed(title="🔮  The Oracle Speaks", description=f"*{text}*", color=0x8E44AD)
        embed.set_footer(text="The Oracle's prophecies are binding. Go forth.")
        await interaction.followup.send(embed=embed)

    # ── /back ─────────────────────────────────────────────────────────────

    @app_commands.command(name="back", description="Pledge your house's gold behind another lord.")
    @app_commands.describe(lord="The lord you wish to back.")
    async def back(self, interaction: discord.Interaction, lord: discord.Member):
        uid  = str(interaction.user.id)
        luid = str(lord.id)
        if uid not in state.user_data:
            await interaction.response.send_message("Register your house first with `/register`.", ephemeral=True); return
        if luid not in state.user_data:
            await interaction.response.send_message(f"{lord.display_name} has no house.", ephemeral=True); return
        if uid == luid:
            await interaction.response.send_message("You cannot back yourself.", ephemeral=True); return
        current = state.user_data[uid].get("backing")
        if current:
            current_name = state.user_data.get(current, {}).get("house", {}).get("name", "another lord")
            await interaction.response.send_message(f"You already back **{current_name}**. Use `/unback` first.", ephemeral=True); return
        state.user_data[uid]["backing"] = luid
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
        lord_house = state.user_data[luid]["house"]
        embed = discord.Embed(
            title="🛡️  Allegiance Pledged",
            description=(
                f"**{state.user_data[uid]['house']['name']}** has pledged their banner to "
                f"**{lord_house['sigil']} {lord_house['name']}**.\n\n"
                f"*\"{lord_house['motto']}\"*\n\n"
                f"You will earn **+{BACKER_WIN_SHARE} gold** on their victories and bleed **{BACKER_LOSS_SHARE} gold** on their defeats."
            ),
            color=lord_house["color"],
        )
        await interaction.response.send_message(embed=embed)

    # ── /unback ───────────────────────────────────────────────────────────

    @app_commands.command(name="unback", description="Renounce your allegiance and back no one.")
    async def unback(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid not in state.user_data:
            await interaction.response.send_message("You are not registered.", ephemeral=True); return
        if not state.user_data[uid].get("backing"):
            await interaction.response.send_message("You have no allegiance to renounce.", ephemeral=True); return
        lord_name = state.user_data.get(state.user_data[uid]["backing"], {}).get("house", {}).get("name", "their lord")
        state.user_data[uid]["backing"]      = None
        state.user_data[uid]["active_wager"] = None
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
        await interaction.response.send_message(f"*Your house has renounced its allegiance to {lord_name}.*", ephemeral=True)

    # ── /wager ────────────────────────────────────────────────────────────

    @app_commands.command(name="wager", description="Bet on whether your backed lord will win or lose their next game.")
    @app_commands.describe(outcome="Your prediction.", amount="Gold to wager. Correct pays 2x.")
    @app_commands.choices(outcome=[
        app_commands.Choice(name="Win",  value="win"),
        app_commands.Choice(name="Loss", value="loss"),
    ])
    async def wager(self, interaction: discord.Interaction, outcome: app_commands.Choice[str], amount: int):
        uid = str(interaction.user.id)
        if uid not in state.user_data:
            await interaction.response.send_message("Register your house first.", ephemeral=True); return
        if not state.user_data[uid].get("backing"):
            await interaction.response.send_message("You must back a lord first with `/back`.", ephemeral=True); return
        if state.user_data[uid].get("active_wager"):
            await interaction.response.send_message("You already have an active wager.", ephemeral=True); return
        if not (BACKER_WAGER_MIN <= amount <= BACKER_WAGER_MAX):
            await interaction.response.send_message(f"Wager must be between {BACKER_WAGER_MIN} and {BACKER_WAGER_MAX} gold.", ephemeral=True); return
        if state.user_data[uid]["gold"] < amount:
            await interaction.response.send_message("Not enough gold.", ephemeral=True); return
        lord_id   = state.user_data[uid]["backing"]
        lord_name = state.user_data.get(lord_id, {}).get("house", {}).get("name", "your lord")
        state.user_data[uid]["active_wager"] = {"lord_id": lord_id, "outcome": outcome.value, "amount": amount}
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
        embed = discord.Embed(
            title="🎲  Wager Placed",
            description=(
                f"**{state.user_data[uid]['house']['name']}** wagered **{amount} gold** that "
                f"**{lord_name}** will **{'WIN' if outcome.value == 'win' else 'LOSE'}** their next game.\n\n"
                f"Correct → **+{amount * 2} 🪙**  ·  Wrong → **-{amount} 🪙**"
            ),
            color=0xF39C12,
        )
        await interaction.response.send_message(embed=embed)

    # ── /joust ────────────────────────────────────────────────────────────

    @app_commands.command(name="joust", description="Challenge another lord to a joust.")
    @app_commands.describe(opponent="The lord you wish to challenge.", wager="Gold each side puts in. Winner takes the pool.")
    async def joust(self, interaction: discord.Interaction, opponent: discord.Member, wager: int):
        uid  = str(interaction.user.id)
        ouid = str(opponent.id)
        if uid not in state.user_data:
            await interaction.response.send_message("Register first.", ephemeral=True); return
        if ouid not in state.user_data:
            await interaction.response.send_message(f"{opponent.display_name} has no house.", ephemeral=True); return
        if uid == ouid:
            await interaction.response.send_message("You cannot joust yourself.", ephemeral=True); return
        active_shame = kingdom.is_shamed(state.user_data[uid])
        if active_shame:
            expires   = state.user_data[uid]["shame"]["expires_at"]
            remaining = max(1, int((expires - time.time()) / 3600))
            await interaction.response.send_message(
                f"You bear **\"{active_shame}\"** and may not joust for another ~{remaining}h. Win a joust to clear it early.",
                ephemeral=True
            ); return
        if not (DUEL_WAGER_MIN <= wager <= DUEL_WAGER_MAX):
            await interaction.response.send_message(f"Wager must be between {DUEL_WAGER_MIN} and {DUEL_WAGER_MAX} gold.", ephemeral=True); return
        if state.user_data[uid]["gold"] < wager:
            await interaction.response.send_message("Not enough gold.", ephemeral=True); return

        # ── One joust at a time ──────────────────────────────────────────
        now = time.time()
        # Clean expired duels first
        expired = [cid for cid, d in state.pending_duels.items() if d["expires_at"] <= now]
        for cid in expired:
            del state.pending_duels[cid]

        # Check if challenger already has a pending joust (as challenger)
        if uid in state.pending_duels:
            await interaction.response.send_message("You already have a pending joust. Wait for it to be accepted or expire.", ephemeral=True); return

        # Check if challenger is already a target in another joust
        for cid, d in state.pending_duels.items():
            if d["target_id"] == uid:
                await interaction.response.send_message("You have a pending joust challenge to answer first. Use `/accept_joust` or wait for it to expire.", ephemeral=True); return

        # Check if the target already has a pending joust (as challenger or target)
        if ouid in state.pending_duels:
            await interaction.response.send_message(f"{opponent.display_name} already has a pending joust.", ephemeral=True); return
        for cid, d in state.pending_duels.items():
            if d["target_id"] == ouid:
                await interaction.response.send_message(f"{opponent.display_name} already has a pending joust.", ephemeral=True); return

        state.pending_duels[uid] = {"target_id": ouid, "wager": wager, "expires_at": now + DUEL_EXPIRY}
        embed = discord.Embed(
            title="🏇  A Joust Has Been Called!",
            description=(
                f"**{state.user_data[uid]['house']['name']}** challenges "
                f"**{state.user_data[ouid]['house']['name']}** for a pool of **{wager*2:,} gold**!\n"
                f"Each side puts in {wager:,} 🪙. Winner takes all.\n\n"
                f"{opponent.mention} — use `/accept_joust` to accept, or ignore to let it expire in 1 hour."
            ),
            color=0xE74C3C,
        )
        await interaction.response.send_message(embed=embed)

    # ── /accept_joust ─────────────────────────────────────────────────────

    @app_commands.command(name="accept_joust", description="Accept a pending joust challenge.")
    async def accept_joust(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)

        # Clean expired duels first
        now = time.time()
        expired = [cid for cid, d in state.pending_duels.items() if d["expires_at"] <= now]
        for cid in expired:
            del state.pending_duels[cid]

        challenger_id = None
        for cid, duel in state.pending_duels.items():
            if duel["target_id"] == uid:
                challenger_id = cid
                break
        if not challenger_id:
            await interaction.response.send_message("No pending joust found for you.", ephemeral=True); return
        if uid not in state.user_data or challenger_id not in state.user_data:
            await interaction.response.send_message("One combatant has no house.", ephemeral=True); return
        duel  = state.pending_duels.pop(challenger_id)
        wager = duel["wager"]
        if state.user_data[uid]["gold"] < wager:
            await interaction.response.send_message("You don't have enough gold to cover the wager.", ephemeral=True); return
        c_power = kingdom.compute_power(state.user_data[challenger_id])
        d_power = kingdom.compute_power(state.user_data[uid])
        total   = c_power + d_power
        c_prob  = c_power / total if total > 0 else 0.5
        challenger_wins = random.random() < c_prob
        winner_id, loser_id = (challenger_id, uid) if challenger_wins else (uid, challenger_id)
        winner = state.user_data[winner_id]
        loser  = state.user_data[loser_id]
        loser["gold"]  = max(0, loser["gold"] - wager)
        winner["gold"] = max(0, winner["gold"] + wager)
        shame         = kingdom.award_shame_title(loser)
        cleared_shame = kingdom.clear_shame(winner)
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
        print(f"[Joust] {winner['house']['name']} beat {loser['house']['name']} for {wager} gold")
        narr        = await narration.narrate_duel_result(winner["house"]["name"], loser["house"]["name"], wager)
        winner_prob = f"{c_prob*100:.0f}%" if challenger_wins else f"{(1-c_prob)*100:.0f}%"
        loser_prob  = f"{(1-c_prob)*100:.0f}%" if challenger_wins else f"{c_prob*100:.0f}%"
        embed = discord.Embed(title="🏇  Joust Resolved!", description=f"*{narr}*", color=0xF39C12)
        embed.add_field(name="🏆 Victor",   value=f"{winner['house']['sigil']} **{winner['house']['name']}**  +{wager:,} 🪙  *(had {winner_prob} odds)*", inline=False)
        embed.add_field(name="💀 Defeated", value=f"{loser['house']['sigil']} **{loser['house']['name']}**  -{wager:,} 🪙  *(had {loser_prob} odds)*",  inline=False)
        embed.add_field(name="😔 Shame",    value=f'"{shame}" — 24h lockout or win a joust to clear', inline=False)
        if cleared_shame:
            embed.add_field(name="✨ Redeemed", value=f'{winner["house"]["name"]} shed the title "{cleared_shame}"', inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /setannouncements ─────────────────────────────────────────────────

    @app_commands.command(name="setannouncements", description="[Admin] Set the kingdom announcements channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setannouncements(self, interaction: discord.Interaction, channel: discord.TextChannel):
        state.announcement_channels[str(interaction.guild_id)] = channel.id
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
        await interaction.response.send_message(f"Announcements set to {channel.mention}.", ephemeral=True)

    # ── /setshame ────────────────────────────────────────────────────────

    @app_commands.command(name="setshame", description="[Admin] Set the Wall of Shame channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setshame(self, interaction: discord.Interaction, channel: discord.TextChannel):
        state.shame_channels[str(interaction.guild_id)] = channel.id
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
        await interaction.response.send_message(f"Shame channel set to {channel.mention}.", ephemeral=True)

    # ── /setgold ─────────────────────────────────────────────────────────

    @app_commands.command(name="setgold", description="[Admin] Set a lord's gold balance.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setgold(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        uid = str(member.id)
        if uid not in state.user_data:
            await interaction.response.send_message("That user has no house.", ephemeral=True); return
        state.user_data[uid]["gold"] = max(0, amount)
        storage.persist_all(state.user_data, state.announcement_channels, state.shame_channels)
        await interaction.response.send_message(f"Set {member.display_name}'s gold to {amount:,}.", ephemeral=True)

    # ── /debugpresence ───────────────────────────────────────────────────

    @app_commands.command(name="debugpresence", description="[Admin] Debug Discord activity for a member.")
    @app_commands.checks.has_permissions(administrator=True)
    async def debugpresence(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        lines  = [f"`{type(a).__name__}` name={a.name!r} state={getattr(a,'state',None)!r}" for a in target.activities]
        await interaction.response.send_message(f"**{target}**\n" + ("\n".join(lines) or "*No activities.*"), ephemeral=True)

    # ── /rules ───────────────────────────────────────────────────────────

    @app_commands.command(name="rules", description="The laws of the Summoner's Court.")
    async def rules(self, interaction: discord.Interaction):
        from bot.config import (
            STARTING_GOLD, WIN_GOLD, LOSS_GOLD, SURRENDER_PENALTY, PENTA_BONUS,
            RANK_UP_BONUS, RANK_DOWN_PENALTY, BACKER_WIN_SHARE, BACKER_LOSS_SHARE,
            BACKER_PENTA_BONUS, BACKER_WAGER_MIN, BACKER_WAGER_MAX,
        )
        embed = discord.Embed(title="📜  Laws of the Summoner's Court", color=0xF1C40F)
        embed.add_field(name="Starting Gold",   value=f"{STARTING_GOLD} 🪙",                  inline=True)
        embed.add_field(name="Win",             value=f"+{WIN_GOLD} 🪙",                       inline=True)
        embed.add_field(name="Loss",            value=f"{LOSS_GOLD} 🪙",                       inline=True)
        embed.add_field(name="Early Surrender", value=f"{SURRENDER_PENALTY} 🪙 extra",         inline=True)
        embed.add_field(name="Pentakill",       value=f"+{PENTA_BONUS} 🪙 💥",                 inline=True)
        embed.add_field(name="Rank Up",         value=f"+{RANK_UP_BONUS} 🪙 🎉",               inline=True)
        embed.add_field(name="Rank Down",       value=f"{RANK_DOWN_PENALTY} 🪙 🔔",            inline=True)
        embed.add_field(name="Joust Range",     value=f"{DUEL_WAGER_MIN}–{DUEL_WAGER_MAX} 🪙", inline=True)
        embed.add_field(
            name="🛡️ Backing",
            value=(
                f"+{BACKER_WIN_SHARE} on lord's win · {BACKER_LOSS_SHARE} on loss · "
                f"+{BACKER_PENTA_BONUS} on pentakill\n"
                f"Wagers: {BACKER_WAGER_MIN}–{BACKER_WAGER_MAX} 🪙 (2x payout)"
            ),
            inline=False,
        )
        embed.add_field(name="Power", value="Gold + (Territory × 10). Everyone on the same leaderboard.", inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Commands(bot))