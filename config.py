import os

# ══════════════════════════════════════════════
#  TOKENS & CLÉS API  (variables d'environnement)
# ══════════════════════════════════════════════
DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN", "")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")

# ══════════════════════════════════════════════
#  PARAMÈTRES BOT
# ══════════════════════════════════════════════
PREFIX          = "!"
LOG_CHANNEL_ID  = 1501172466251468812

# ══════════════════════════════════════════════
#  MODÉRATION — SEUILS
# ══════════════════════════════════════════════
WARN_MUTE       = 3          # warns → mute (10 min)
WARN_KICK       = 5          # warns → kick
WARN_BAN        = 7          # warns → ban
MUTE_DURATION   = 600        # secondes (10 min)

# Spam : X messages identiques en Y secondes
SPAM_COUNT      = 5
SPAM_WINDOW     = 8          # secondes
CAPS_RATIO      = 0.7        # 70% majuscules = spam

# Anti-raid : X joins en Y secondes
RAID_JOIN_COUNT = 10
RAID_JOIN_WINDOW= 15         # secondes
NEW_ACCOUNT_DAYS= 7          # compte < 7 jours = suspect

# ══════════════════════════════════════════════
#  ÉCONOMIE
# ══════════════════════════════════════════════
DAILY_REWARD    = 100        # coins par /daily
DAILY_COOLDOWN  = 86400      # 24h en secondes
QUIZ_REWARD     = 10         # coins par bonne réponse
QUIZ_TIMER      = 30         # secondes pour répondre

SHOP_ITEMS = {
    "vip": {
        "name":  "Rôle VIP",
        "price": 500,
        "type":  "role",
        "role_name": "VIP",
        "description": "Obtiens le rôle VIP exclusif"
    },
    "legende": {
        "name":  "Titre Légende",
        "price": 1000,
        "type":  "role",
        "role_name": "Légende",
        "description": "Titre de prestige : Légende"
    },
    "dieu": {
        "name":  "Titre Dieu",
        "price": 2500,
        "type":  "role",
        "role_name": "Dieu",
        "description": "Titre ultime : Dieu"
    },
}

# ══════════════════════════════════════════════
#  LISTE INSULTES / MOTS BANNIS  (exemples)
# ══════════════════════════════════════════════
BANNED_WORDS = [
    "insulte1", "insulte2", "insulte3",   # ← remplace par ta liste réelle
    "badword",  "slur",
]

# Patterns regex pour contournements courants (l33t speak, etc.)
BANNED_PATTERNS = [
    r"i+n+s+u+l+t+e",          # lettres répétées
    r"b[4a@]dw[o0]rd",          # substitutions
]

# Domaines suspects (liens)
SUSPICIOUS_DOMAINS = [
    "grabify", "iplogger", "discord.gift",
    "discordnitro", "steamcommunity.ru",
]

# ══════════════════════════════════════════════
#  KEEP ALIVE
# ══════════════════════════════════════════════
FLASK_PORT = 10000
