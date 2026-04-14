# ⚔️ The Summoner's Court

A League of Legends Discord bot where your server becomes a medieval kingdom.
Every ranked game you play changes the world — gold flows, territory shifts, duels are declared, and the Royal Herald narrates it all with AI-generated dramatic flair.

---

## How It Works

1. **Discord Presence** detects when a registered player starts/stops a League of Legends ranked game
2. When the game ends, the bot fetches the match from **Riot's Match-v5 API**
3. Gold, territory, and rank changes are calculated and applied to your **house**
4. The **Claude API** generates a dramatic fantasy narration of the result and posts it to your announcements channel
5. Rank promotions trigger glory announcements; demotions ring the **shame bell** 🔔

No polling. Discord handles game detection; Riot API is only hit when a game ends.

---

## Features

### 🏰 House System
When you register, the bot generates a unique noble house based on your champion pool:
> *"House Obsidian Rift — Sigil: 🐉 — Words: 'Feed Once, Feast Forever.'"*

### 💰 Kingdom Economy

| Event | Gold |
|---|---|
| Ranked Win | +75 |
| Ranked Loss | -30 |
| Early Surrender (<20 min) | -50 extra |
| Pentakill | +200 |
| Rank Up | +150 |
| Rank Down | -100 |

**Power** = Gold + (Territory × 10). Power determines leaderboard rank.

### 🤖 AI Narration
Every match result, duel, and weekly recap is narrated by the Royal Herald — a dramatic fantasy voice powered by the Claude API.

### ⚔️ Duels
Challenge a lord for 50–500 gold. Outcome is based on recent win-rates plus randomness. Loser gets a shame title.

### 🕵️ Spies
Spend 75 gold to secretly view another lord's last 5 ranked games.

### 🔮 Oracle
`/oracle [champion]` delivers a cryptic prophecy before you queue.

### 🔔 Shame Bell
Every demotion posts a mocking AI-written eulogy to the shame channel.

### 📜 Weekly Chronicle
Sunday at 8 PM UTC — an AI-written recap of the week's battles, promotions, and pentakills.

---

## Commands

| Command | Description |
|---|---|
| `/register <name> <tag> [region]` | Forge your house |
| `/unregister` | Dissolve your house |
| `/house [@member]` | View a house |
| `/leaderboard` | Power rankings |
| `/oracle <champion>` | Pre-game prophecy |
| `/duel @member <wager>` | Challenge a lord |
| `/accept_duel` | Accept a pending duel |
| `/spy @member` | Peek at recent games |
| `/rules` | View economy rules |
| `/setannouncements #channel` | [Admin] Set announcements channel |
| `/setshame #channel` | [Admin] Set shame channel |
| `/setgold @member <amount>` | [Admin] Adjust gold |
| `/debugpresence [@member]` | [Admin] Debug activity data |

---

## Setup

### 1. Discord Bot
1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application
2. Bot → Enable **Presence Intent**, **Server Members Intent**, **Message Content Intent**
3. OAuth2 → Scopes: `bot`, `applications.commands` → Permissions: Send Messages, Embed Links, Use Slash Commands

### 2. API Keys
- **Riot**: [developer.riotgames.com](https://developer.riotgames.com)
- **Anthropic**: [console.anthropic.com](https://console.anthropic.com)

### 3. Environment
```bash
cp .env.example .env
# Fill in DISCORD_BOT_TOKEN, RIOT_API_KEY, ANTHROPIC_API_KEY
```

### 4. Run
```bash
pip install -r requirements.txt
python run.py
```

---

## Project Structure

```
bot/
├── main.py         # Entry point — creates bot, loads cogs
├── config.py       # All constants and tuning knobs
├── state.py        # Shared mutable runtime state
├── storage.py      # JSON persistence (data/kingdom.json)
├── riot_api.py     # Riot API client (Match-v5, Summoner-v4, League-v4)
├── presence.py     # LoL game detection via Discord presence
├── kingdom.py      # House generation, gold/territory/rank logic
├── narration.py    # Claude API — all AI narration
├── helpers.py      # Discord embed builders
└── cogs/
    ├── events.py   # Presence listener, match pipeline, weekly recap
    └── commands.py # All slash commands
run.py
```

---

## Architecture

```
Discord Presence
    │
    ├── "In Game" detected → record start time
    │
    └── Activity disappears
          └── Wait 90s → Riot Match-v5 API
                ├── Apply gold / territory
                ├── Check rank change
                ├── Claude API → narration
                └── Post embed → announcements / shame channel
```

## Notes

- Players must have **"Display current activity"** enabled in Discord settings.
- Personal Riot API keys expire every 24h — use a production key for persistent hosting.
- Data lives in `data/kingdom.json` — back it up when deploying to the cloud.
- Use `/debugpresence` if game detection isn't firing.
