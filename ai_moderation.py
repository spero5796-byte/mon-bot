"""
ai_moderation.py
Analyse de messages via OpenAI avec fallback automatique.
Retourne YES / NO — ne fait jamais crasher le bot.
"""

import re
import asyncio
from openai import AsyncOpenAI
import config

# Client OpenAI (initialisé une seule fois)
_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None and config.OPENAI_API_KEY:
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return _client


# ── Analyse locale (sans IA) ───────────────────────────────
def local_check(content: str) -> bool:
    """
    Vérifie le contenu avec la liste de mots bannis et les patterns regex.
    Retourne True si le message est suspect.
    """
    lower = content.lower()

    # Mots bannis directs
    for word in config.BANNED_WORDS:
        if word in lower:
            return True

    # Patterns regex (contournements l33t speak, etc.)
    for pattern in config.BANNED_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return True

    # Liens suspects
    for domain in config.SUSPICIOUS_DOMAINS:
        if domain in lower:
            return True

    return False


def spam_check(content: str) -> str | None:
    """
    Vérifie si le message est du spam (majuscules excessives, etc.).
    Retourne la raison ou None.
    """
    # Trop de majuscules
    letters = [c for c in content if c.isalpha()]
    if len(letters) > 10:
        ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if ratio >= config.CAPS_RATIO:
            return "spam_caps"

    return None


# ── Analyse IA (OpenAI) ────────────────────────────────────
async def ai_check(content: str) -> bool:
    """
    Envoie le message à OpenAI pour analyse.
    Retourne True si toxique, False sinon.
    En cas d'erreur, retourne False (fallback sécurisé).
    """
    client = get_client()
    if not client:
        return False  # Pas de clé API configurée

    prompt = (
        "Tu es un modérateur Discord. Analyse ce message et réponds UNIQUEMENT par YES si "
        "le message est toxique, insultant, haineux, menaçant ou inapproprié, ou NO sinon. "
        "Prends en compte les contournements (l33t speak, espaces entre lettres, etc.).\n\n"
        f"Message : {content}"
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0,
            ),
            timeout=8.0  # timeout 8 secondes
        )
        answer = response.choices[0].message.content.strip().upper()
        return answer.startswith("YES")

    except asyncio.TimeoutError:
        print("[AI] Timeout OpenAI — fallback local")
        return False
    except Exception as e:
        print(f"[AI] Erreur OpenAI : {e} — fallback local")
        return False


# ── Point d'entrée principal ───────────────────────────────
async def analyze_message(content: str) -> tuple[bool, str]:
    """
    Analyse complète d'un message.
    Retourne (is_toxic: bool, reason: str).
    Ordre : local → spam → IA
    """
    # 1. Vérification locale rapide
    if local_check(content):
        return True, "contenu_interdit"

    # 2. Vérification spam
    spam_reason = spam_check(content)
    if spam_reason:
        return True, spam_reason

    # 3. Analyse IA
    toxic = await ai_check(content)
    if toxic:
        return True, "ia_detection"

    return False, ""


# ── Génération de question quiz ────────────────────────────
async def generate_quiz_question(category: str = "culture générale") -> dict | None:
    """
    Génère une question de quiz via OpenAI.
    Retourne un dict ou None en cas d'erreur.
    """
    client = get_client()
    if not client:
        return _fallback_question(category)

    prompt = (
        f"Génère une question de quiz sur : {category}.\n"
        "Réponds UNIQUEMENT en JSON valide sans markdown :\n"
        '{"question":"...","options":{"A":"...","B":"...","C":"...","D":"..."},'
        '"answer":"A","explication":"..."}\n'
        "La bonne réponse doit varier entre A, B, C, D."
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.9,
            ),
            timeout=15.0
        )
        import json
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)

    except Exception as e:
        print(f"[AI] Erreur génération quiz : {e}")
        return _fallback_question(category)


def _fallback_question(category: str) -> dict:
    """Question de secours si l'IA est indisponible."""
    return {
        "question": f"Quelle est la capitale de la France ? (question de secours — {category})",
        "options": {"A": "Paris", "B": "Lyon", "C": "Marseille", "D": "Bordeaux"},
        "answer": "A",
        "explication": "Paris est la capitale de la France depuis des siècles."
    }
