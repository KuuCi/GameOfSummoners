# ─────────────────────────────────────────────
#  The Summoner's Court  ·  config.py
# ─────────────────────────────────────────────

# ── Timing ──────────────────────────────────
MATCH_FETCH_DELAY     = 90    # Seconds to wait after game ends before hitting Riot API
RESULTS_WAIT_TIME     = 40    # Seconds to wait for squad-mates before posting results
DUEL_EXPIRY           = 3600  # Seconds before an unaccepted duel expires (1 hour)
WEEKLY_RECAP_DAY      = 6     # Weekday for weekly recap post (0=Mon … 6=Sun)
WEEKLY_RECAP_HOUR     = 20    # Hour (UTC) to post weekly recap

# ── Kingdom Economy ─────────────────────────
STARTING_GOLD         = 500   # Gold every new house begins with
WIN_GOLD              = 75    # Gold awarded for a ranked win
LOSS_GOLD             = -30   # Gold change for a ranked loss
SURRENDER_PENALTY     = -50   # Extra deduction if game ends via early surrender (<20 min)
MVP_BONUS             = 50    # Awarded to the highest KDA player in a group game
PENTA_BONUS           = 200   # Pentakill earns this much gold (very rare, very loud)
RANK_UP_BONUS         = 150   # Promoted to a new division
RANK_DOWN_PENALTY     = -100  # Demoted (triggers the shame bell 🔔)
DUEL_WAGER_MIN        = 50
DUEL_WAGER_MAX        = 500

# ── Backer / Vassal System ──────────────────
SHAME_DURATION        = 86400  # Shame title expires after 24 hours
BACKER_WIN_SHARE      = 30    # Gold a vassal earns when their lord wins
BACKER_LOSS_SHARE     = -15   # Gold a vassal loses when their lord loses
BACKER_PENTA_BONUS    = 75    # Extra gold for vassals when their lord gets a pentakill
BACKER_WAGER_MIN      = 25
BACKER_WAGER_MAX      = 300

# ── Territory / Power ────────────────────────
# Each win adds TERRITORY_PER_WIN to your house's land count.
# Power = gold + (territory * TERRITORY_GOLD_VALUE)
TERRITORY_PER_WIN     = 1
TERRITORY_LOST_PER_LOSS = 0   # Territory is never lost — only won or declared via war
TERRITORY_GOLD_VALUE  = 10    # Each territory tile is worth this much in power calculations

# ── Riot API ────────────────────────────────
# Supported regions → routing values
ROUTING = {
    "na1":  "americas",
    "br1":  "americas",
    "la1":  "americas",
    "la2":  "americas",
    "euw1": "europe",
    "eun1": "europe",
    "tr1":  "europe",
    "ru":   "europe",
    "kr":   "asia",
    "jp1":  "asia",
    "oc1":  "sea",
    "ph2":  "sea",
    "sg2":  "sea",
    "th2":  "sea",
    "tw2":  "sea",
    "vn2":  "sea",
}

DEFAULT_REGION = "na1"

# ── Discord Presence ─────────────────────────
LOL_APP_ID        = "401518684763586560"   # Official League of Legends Discord app ID
LOL_APP_NAME      = "League of Legends"
IN_GAME_STATE     = "In Game"

# ── House Generation ─────────────────────────
HOUSE_ADJECTIVES = [
    "Iron", "Storm", "Void", "Silver", "Gilded", "Crimson", "Twilight",
    "Ashen", "Golden", "Obsidian", "Cursed", "Blessed", "Fallen", "Rising",
    "Shattered", "Ancient", "Infernal", "Celestial", "Forsaken", "Radiant",
]
HOUSE_NOUNS = [
    "Drake", "Baron", "Nexus", "Rift", "Turret", "Herald", "Bramble",
    "Fang", "Crest", "Ward", "Chalice", "Blade", "Crown", "Sigil", "Pyre",
    "Rune", "Veil", "Forge", "Throne", "Abyss",
]
HOUSE_MOTTOS = [
    "We Scale.", "Death Before Surrender.", "Gold Flows Upward.",
    "In Chaos, Carry.", "The Lane Never Forgets.", "Wards Win Wars.",
    "Support Gap.", "6Pek Followers.", "Gank Or Be Ganked.",
    "Honor The Reset Timer.", "Vision Is Power.", "Tilt Builds Character.",
    "We Were 4v5.", "Push. Push. Push.", "Top Diff.",
]

# ── Shame & Glory Titles ─────────────────────
SHAME_TITLES = [
    "The Inting Menace",
    "Professional Feeder",
    "Hardstuck Forever",
    "Courier for the Enemy",
    "Village Idiot",
    "Bottom of the Food Chain",
    "The Liability",
    "Certified Trollpick",
    "Carried by Teammates",
    "The Reason We Lost",
    "Negative KDA haver",
    "Killable Demon King",
]
GLORY_TITLES = [
    "The Unkillable Demon King", "Scourge of the Rift", "The Edge of Infinity",
    "6Pek Acolyte", "The Unseen Hand", "Dragon Sovereign", 
    "Keeper of the Void", "Herald of the Baron",
    "The Uncontested", "Champion of Champions",
]

# ── Narration ────────────────────────────────
NARRATION_MODEL = "claude-sonnet-4-20250514"