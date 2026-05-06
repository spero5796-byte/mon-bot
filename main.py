"""
main.py
Bot Discord ultra complet — modération IA, quiz, économie, anti-raid, logs.
Structure : discord.py + Cogs + SQLite + OpenAI
"""

import asyncio
import time
import re
from collections import defaultdict, deque

import discord
from discord.ext import commands, tasks

import config
import database as db
import ai_moderation as ai
from keep_alive import keep_alive

# ══════════════════════════════════════════════════════════════
#  INTENTS & BOT
# ══════════════════════════════════════════════════════════════
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=config.PREFIX,
    intents=intents,
    help_command=None,          # on écrit le nôtre
    case_insensitive=True,
)

# ══════════════════════════════════════════════════════════════
#  ÉTAT EN MÉMOIRE
# ══════════════════════════════════════════════════════════════

# Spam tracker  { user_id: deque([timestamps]) }
spam_tracker: dict[int, deque] = defaultdict(lambda: deque())

# Anti-raid     { guild_id: deque([timestamps]) }
raid_tracker: dict[int, deque] = defaultdict(lambda: deque())

# Quiz actif    { channel_id: {question, answer, explication, answered_users, task} }
active_quizzes: dict[int, dict] = {}

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def embed(title: str, description: str = "", color: discord.Color = discord.Color.blurple()) -> discord.Embed:
    """Crée un embed standardisé."""
    e = discord.Embed(title=title, description=description, color=color)
    e.timestamp = discord.utils.utcnow()
    return e


async def send_log(guild: discord.Guild, title: str, description: str, color: discord.Color = discord.Color.red()):
    """Envoie un message dans le salon de logs."""
    ch = guild.get_channel(config.LOG_CHANNEL_ID)
    if ch:
        try:
            await ch.send(embed=embed(title, description, color))
        except discord.Forbidden:
            pass


async def apply_sanction(member: discord.Member, warn_count: int, reason: str):
    """Applique la sanction correspondant au nombre de warns."""
    guild = member.guild

    if warn_count >= config.WARN_BAN:
        try:
            await member.ban(reason=f"[AutoMod] {warn_count} warns — {reason}")
            await send_log(guild, "🔨 BAN automatique",
                           f"{member.mention} banni après {warn_count} warns.\nRaison : {reason}")
        except discord.Forbidden:
            pass

    elif warn_count >= config.WARN_KICK:
        try:
            await member.kick(reason=f"[AutoMod] {warn_count} warns — {reason}")
            await send_log(guild, "👟 KICK automatique",
                           f"{member.mention} expulsé après {warn_count} warns.\nRaison : {reason}")
        except discord.Forbidden:
            pass

    elif warn_count >= config.WARN_MUTE:
        try:
            until = discord.utils.utcnow() + discord.utils.timedelta(seconds=config.MUTE_DURATION)
            await member.timeout(until, reason=f"[AutoMod] {warn_count} warns")
            await send_log(guild, "🔇 MUTE automatique",
                           f"{member.mention} muté 10 min après {warn_count} warns.")
        except discord.Forbidden:
            pass


# ══════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    db.init_db()
    print(f"✅ Bot connecté : {bot.user} | {len(bot.guilds)} serveur(s)")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="!help | votre serveur")
    )


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    now = time.time()

    # ── Anti-raid : comptage des joins récents ──
    q = raid_tracker[guild.id]
    q.append(now)
    cutoff = now - config.RAID_JOIN_WINDOW
    while q and q[0] < cutoff:
        q.popleft()

    if len(q) >= config.RAID_JOIN_COUNT:
        await send_log(guild, "⚠️ RAID DÉTECTÉ",
                       f"{len(q)} membres ont rejoint en {config.RAID_JOIN_WINDOW}s.\n"
                       "Slowmode automatique activé.", discord.Color.orange())
        # Slowmode sur tous les salons textuels
        for ch in guild.text_channels:
            try:
                await ch.edit(slowmode_delay=30)
            except discord.Forbidden:
                pass

    # ── Compte suspect (nouveau compte) ──
    age_days = (discord.utils.utcnow() - member.created_at).days
    if age_days < config.NEW_ACCOUNT_DAYS:
        await send_log(guild, "🆕 Compte suspect",
                       f"{member.mention} a rejoint (compte créé il y a **{age_days}j**).",
                       discord.Color.yellow())

    await send_log(guild, "✅ Membre rejoint",
                   f"{member.mention} (`{member.id}`) a rejoint le serveur.",
                   discord.Color.green())


@bot.event
async def on_member_remove(member: discord.Member):
    await send_log(member.guild, "🚪 Membre parti",
                   f"{member.name} (`{member.id}`) a quitté le serveur.",
                   discord.Color.greyple())


@bot.event
async def on_message(message: discord.Message):
    # Ignorer les bots et les DM
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    # Ignorer les modérateurs
    if message.author.guild_permissions.manage_messages:
        await bot.process_commands(message)
        return

    content = message.content
    now = time.time()
    author = message.author

    # ── 1. Détection spam répétitif ──────────────────────────
    uid = author.id
    q = spam_tracker[uid]
    q.append((now, content))
    cutoff = now - config.SPAM_WINDOW
    while q and q[0][0] < cutoff:
        q.popleft()

    recent_contents = [m for _, m in q]
    is_spam_repeat = len(recent_contents) >= config.SPAM_COUNT and \
                     recent_contents.count(content) >= config.SPAM_COUNT

    if is_spam_repeat:
        await message.delete()
        warn_count = db.add_warn(uid, message.guild.id, "spam répétitif", bot.user.id)
        await message.channel.send(
            embed=embed("🚫 Spam détecté",
                        f"{author.mention}, arrête le spam ! (**{warn_count}** warn(s))",
                        discord.Color.orange()),
            delete_after=5
        )
        await send_log(message.guild, "⚠️ Spam",
                       f"{author.mention} | spam répétitif | {warn_count} warn(s)")
        await apply_sanction(author, warn_count, "spam répétitif")
        return

    # ── 2. Analyse IA + local ────────────────────────────────
    is_toxic, reason = await ai.analyze_message(content)

    if is_toxic:
        try:
            await message.delete()
        except discord.NotFound:
            pass
        warn_count = db.add_warn(uid, message.guild.id, reason, bot.user.id)
        await message.channel.send(
            embed=embed("🚫 Message supprimé",
                        f"{author.mention}, ton message a été supprimé (**{warn_count}** warn(s))",
                        discord.Color.red()),
            delete_after=5
        )
        await send_log(message.guild, "🗑️ Message supprimé",
                       f"**Auteur :** {author.mention}\n"
                       f"**Raison :** `{reason}`\n"
                       f"**Warns :** {warn_count}\n"
                       f"**Contenu :** ```{content[:300]}```")
        await apply_sanction(author, warn_count, reason)
        return

    # ── 3. Quiz : vérification de réponse en attente ─────────
    quiz = active_quizzes.get(message.channel.id)
    if quiz and content.upper() in ("A", "B", "C", "D"):
        if uid not in quiz["answered_users"]:
            quiz["answered_users"].add(uid)
            correct = content.upper() == quiz["answer"]
            db.record_quiz_answer(uid, correct)
            if correct:
                coins = db.add_coins(uid, config.QUIZ_REWARD)
                await message.channel.send(
                    embed=embed("✅ Bonne réponse !",
                                f"{author.mention} a trouvé la bonne réponse !\n"
                                f"**{quiz['answer']}** — {quiz['explication']}\n"
                                f"💰 +{config.QUIZ_REWARD} coins → Total : **{coins}**",
                                discord.Color.green())
                )
            else:
                await message.channel.send(
                    embed=embed("❌ Mauvaise réponse",
                                f"{author.mention}, ce n'est pas la bonne réponse.",
                                discord.Color.red()),
                    delete_after=4
                )

    await bot.process_commands(message)


# ══════════════════════════════════════════════════════════════
#  COMMANDES — MODÉRATION
# ══════════════════════════════════════════════════════════════

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn_cmd(ctx, member: discord.Member, *, reason: str = "Aucune raison"):
    warn_count = db.add_warn(member.id, ctx.guild.id, reason, ctx.author.id)
    await ctx.send(embed=embed("⚠️ Avertissement",
                               f"{member.mention} a reçu un warn. (**{warn_count}** total)\nRaison : {reason}",
                               discord.Color.yellow()))
    await send_log(ctx.guild, "⚠️ WARN",
                   f"**Modérateur :** {ctx.author.mention}\n"
                   f"**Cible :** {member.mention}\n"
                   f"**Raison :** {reason}\n"
                   f"**Total warns :** {warn_count}")
    await apply_sanction(member, warn_count, reason)


@bot.command(name="clearwarn")
@commands.has_permissions(manage_messages=True)
async def clearwarn_cmd(ctx, member: discord.Member):
    db.clear_warns(member.id, ctx.guild.id)
    await ctx.send(embed=embed("🗑️ Warns effacés",
                               f"Les warns de {member.mention} ont été supprimés.",
                               discord.Color.green()))
    await send_log(ctx.guild, "🗑️ CLEARWARN",
                   f"**Modérateur :** {ctx.author.mention}\n**Cible :** {member.mention}")


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute_cmd(ctx, member: discord.Member, duration: int = 10, *, reason: str = "Aucune raison"):
    until = discord.utils.utcnow() + discord.utils.timedelta(minutes=duration)
    await member.timeout(until, reason=reason)
    await ctx.send(embed=embed("🔇 Mute",
                               f"{member.mention} muté **{duration} min**.\nRaison : {reason}",
                               discord.Color.orange()))
    await send_log(ctx.guild, "🔇 MUTE",
                   f"**Modérateur :** {ctx.author.mention}\n"
                   f"**Cible :** {member.mention}\n"
                   f"**Durée :** {duration} min\n**Raison :** {reason}")


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute_cmd(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(embed=embed("🔊 Unmute",
                               f"{member.mention} n'est plus muté.",
                               discord.Color.green()))
    await send_log(ctx.guild, "🔊 UNMUTE",
                   f"**Modérateur :** {ctx.author.mention}\n**Cible :** {member.mention}")


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_cmd(ctx, member: discord.Member, *, reason: str = "Aucune raison"):
    await member.kick(reason=reason)
    await ctx.send(embed=embed("👟 Kick",
                               f"{member.mention} a été expulsé.\nRaison : {reason}",
                               discord.Color.orange()))
    await send_log(ctx.guild, "👟 KICK",
                   f"**Modérateur :** {ctx.author.mention}\n"
                   f"**Cible :** {member.name} (`{member.id}`)\n**Raison :** {reason}")


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_cmd(ctx, member: discord.Member, *, reason: str = "Aucune raison"):
    await member.ban(reason=reason)
    await ctx.send(embed=embed("🔨 Ban",
                               f"{member.mention} a été banni.\nRaison : {reason}",
                               discord.Color.red()))
    await send_log(ctx.guild, "🔨 BAN",
                   f"**Modérateur :** {ctx.author.mention}\n"
                   f"**Cible :** {member.name} (`{member.id}`)\n**Raison :** {reason}")


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_cmd(ctx, user_id: int):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(embed=embed("✅ Unban", f"{user} a été débanni.", discord.Color.green()))
        await send_log(ctx.guild, "✅ UNBAN",
                       f"**Modérateur :** {ctx.author.mention}\n**Cible :** {user} (`{user_id}`)")
    except discord.NotFound:
        await ctx.send("❌ Utilisateur introuvable ou non banni.")


@bot.command(name="warns")
@commands.has_permissions(manage_messages=True)
async def warns_cmd(ctx, member: discord.Member):
    warns = db.get_warns(member.id, ctx.guild.id)
    if not warns:
        await ctx.send(embed=embed("✅ Aucun warn", f"{member.mention} est clean !", discord.Color.green()))
        return
    desc = "\n".join([f"**{i+1}.** {w['reason']} — <t:{int(w['timestamp'])}:R>" for i, w in enumerate(warns)])
    await ctx.send(embed=embed(f"⚠️ Warns de {member.name}", desc, discord.Color.yellow()))


# ══════════════════════════════════════════════════════════════
#  COMMANDES — QUIZ
# ══════════════════════════════════════════════════════════════

@bot.command(name="quiz")
@commands.cooldown(1, 5, commands.BucketType.channel)
async def quiz_cmd(ctx, *, category: str = "culture générale"):
    if ctx.channel.id in active_quizzes:
        await ctx.send("❌ Un quiz est déjà en cours dans ce salon ! Attends qu'il se termine.")
        return

    msg = await ctx.send(embed=embed("🎲 Quiz", "Génération de la question...", discord.Color.blurple()))

    q = await ai.generate_quiz_question(category)
    if not q:
        await msg.edit(content="❌ Impossible de générer une question. Réessaie.", embed=None)
        return

    quiz_embed = discord.Embed(
        title=f"❓ Quiz — {category.title()}",
        description=f"**{q['question']}**",
        color=discord.Color.blurple()
    )
    for letter, text in q["options"].items():
        quiz_embed.add_field(name=letter, value=text, inline=True)
    quiz_embed.set_footer(text=f"Réponds avec A, B, C ou D — Temps : {config.QUIZ_TIMER}s")

    await msg.edit(embed=quiz_embed)

    active_quizzes[ctx.channel.id] = {
        "question":       q["question"],
        "answer":         q["answer"],
        "explication":    q["explication"],
        "answered_users": set(),
        "message_id":     msg.id,
    }

    # Timer — clôture automatique après QUIZ_TIMER secondes
    await asyncio.sleep(config.QUIZ_TIMER)

    if ctx.channel.id in active_quizzes:
        del active_quizzes[ctx.channel.id]
        timeout_embed = discord.Embed(
            title="⏰ Temps écoulé !",
            description=f"La bonne réponse était **{q['answer']}** — {q['explication']}",
            color=discord.Color.orange()
        )
        await ctx.channel.send(embed=timeout_embed)


@bot.command(name="stopquiz")
@commands.has_permissions(manage_messages=True)
async def stopquiz_cmd(ctx):
    if ctx.channel.id not in active_quizzes:
        await ctx.send("❌ Aucun quiz en cours dans ce salon.")
        return
    q = active_quizzes.pop(ctx.channel.id)
    await ctx.send(embed=embed("🛑 Quiz arrêté",
                               f"La bonne réponse était **{q['answer']}** — {q['explication']}",
                               discord.Color.orange()))


@bot.command(name="top")
async def top_cmd(ctx):
    rows = db.get_quiz_leaderboard(10)
    if not rows:
        await ctx.send("Aucun score enregistré pour l'instant.")
        return
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f"**{i+1}.**"
        user = bot.get_user(row["user_id"]) or f"User#{row['user_id']}"
        pct = round(row["correct"] / row["total"] * 100) if row["total"] else 0
        lines.append(f"{medal} {user} — {row['correct']}/{row['total']} ({pct}%)")
    await ctx.send(embed=embed("🏆 Top Quiz", "\n".join(lines), discord.Color.gold()))


# ══════════════════════════════════════════════════════════════
#  COMMANDES — ÉCONOMIE
# ══════════════════════════════════════════════════════════════

@bot.command(name="coins")
async def coins_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    coins = db.get_coins(target.id)
    await ctx.send(embed=embed("💰 Solde",
                               f"{target.mention} possède **{coins} coins**.",
                               discord.Color.gold()))


@bot.command(name="daily")
async def daily_cmd(ctx):
    uid = ctx.author.id
    last = db.get_last_daily(uid)
    elapsed = time.time() - last

    if elapsed < config.DAILY_COOLDOWN:
        remaining = int(config.DAILY_COOLDOWN - elapsed)
        h, m = divmod(remaining // 60, 60)
        await ctx.send(embed=embed("⏳ Daily déjà réclamé",
                                   f"Reviens dans **{h}h {m}min**.",
                                   discord.Color.orange()))
        return

    coins = db.add_coins(uid, config.DAILY_REWARD)
    db.set_last_daily(uid)
    await ctx.send(embed=embed("🎁 Daily reward",
                               f"{ctx.author.mention} a reçu **{config.DAILY_REWARD} coins** !\n"
                               f"💰 Solde total : **{coins} coins**",
                               discord.Color.green()))


@bot.command(name="shop")
async def shop_cmd(ctx):
    e = discord.Embed(title="🛒 Boutique", color=discord.Color.blurple())
    for item_id, item in config.SHOP_ITEMS.items():
        e.add_field(
            name=f"{item['name']} — {item['price']} coins",
            value=f"{item['description']}\n`!buy {item_id}`",
            inline=False
        )
    await ctx.send(embed=e)


@bot.command(name="buy")
async def buy_cmd(ctx, item_id: str):
    item_id = item_id.lower()
    item = config.SHOP_ITEMS.get(item_id)
    if not item:
        await ctx.send(f"❌ Article `{item_id}` introuvable. Consulte `!shop`.")
        return

    uid = ctx.author.id

    if db.has_item(uid, item_id):
        await ctx.send(f"❌ Tu possèdes déjà **{item['name']}**.")
        return

    coins = db.get_coins(uid)
    if coins < item["price"]:
        await ctx.send(embed=embed("❌ Fonds insuffisants",
                                   f"Il te faut **{item['price']} coins**. Tu en as **{coins}**.",
                                   discord.Color.red()))
        return

    # Déduire les coins
    db.add_coins(uid, -item["price"])
    db.add_item(uid, item_id)

    # Attribuer le rôle si disponible
    if item["type"] == "role":
        role = discord.utils.get(ctx.guild.roles, name=item["role_name"])
        if role:
            try:
                await ctx.author.add_roles(role, reason=f"Achat boutique : {item['name']}")
            except discord.Forbidden:
                await ctx.send("⚠️ Impossible d'attribuer le rôle (permissions insuffisantes).")

    new_balance = db.get_coins(uid)
    await ctx.send(embed=embed("✅ Achat réussi",
                               f"Tu as acheté **{item['name']}** !\n💰 Solde restant : **{new_balance} coins**",
                               discord.Color.green()))


@bot.command(name="profil")
async def profil_cmd(ctx, member: discord.Member = None):
    target = member or ctx.author
    uid = target.id
    coins = db.get_coins(uid)
    warns = db.get_warns(uid, ctx.guild.id)
    inventory = db.get_inventory(uid)
    rows = db.get_quiz_leaderboard(999)
    quiz_row = next((r for r in rows if r["user_id"] == uid), None)

    e = discord.Embed(title=f"👤 Profil de {target.display_name}", color=discord.Color.blurple())
    e.set_thumbnail(url=target.display_avatar.url)
    e.add_field(name="💰 Coins", value=str(coins), inline=True)
    e.add_field(name="⚠️ Warns", value=str(len(warns)), inline=True)

    if quiz_row:
        pct = round(quiz_row["correct"] / quiz_row["total"] * 100) if quiz_row["total"] else 0
        e.add_field(name="🎮 Quiz", value=f"{quiz_row['correct']}/{quiz_row['total']} ({pct}%)", inline=True)

    inv_display = ", ".join([config.SHOP_ITEMS[i]["name"] for i in inventory if i in config.SHOP_ITEMS]) or "Vide"
    e.add_field(name="🎒 Inventaire", value=inv_display, inline=False)
    e.add_field(name="📅 Compte créé", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=True)

    await ctx.send(embed=e)


# ══════════════════════════════════════════════════════════════
#  COMMANDE — AIDE
# ══════════════════════════════════════════════════════════════

@bot.command(name="help")
async def help_cmd(ctx):
    e = discord.Embed(title="📖 Aide du bot", color=discord.Color.blurple())

    e.add_field(name="🔐 Modération", value=(
        "`!warn @user raison` — avertir\n"
        "`!mute @user [min] raison` — muter\n"
        "`!unmute @user` — démuter\n"
        "`!kick @user raison` — expulser\n"
        "`!ban @user raison` — bannir\n"
        "`!unban ID` — débannir\n"
        "`!warns @user` — voir warns\n"
        "`!clearwarn @user` — effacer warns"
    ), inline=False)

    e.add_field(name="🎮 Quiz", value=(
        "`!quiz [catégorie]` — lancer un quiz\n"
        "`!stopquiz` — arrêter le quiz\n"
        "`!top` — classement quiz"
    ), inline=False)

    e.add_field(name="💰 Économie", value=(
        "`!coins [@user]` — voir les coins\n"
        "`!daily` — récompense quotidienne\n"
        "`!shop` — boutique\n"
        "`!buy <item>` — acheter un article\n"
        "`!profil [@user]` — voir le profil"
    ), inline=False)

    await ctx.send(embed=e)


# ══════════════════════════════════════════════════════════════
#  GESTION D'ERREURS GLOBALE
# ══════════════════════════════════════════════════════════════

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.", delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable.", delete_after=5)
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Attends {error.retry_after:.1f}s avant de réutiliser cette commande.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument manquant : `{error.param.name}`\nUtilise `!help` pour voir la syntaxe.", delete_after=8)
    else:
        print(f"[ERREUR] {ctx.command} : {error}")


# ══════════════════════════════════════════════════════════════
#  LANCEMENT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    keep_alive()                        # Flask sur port 10000
    bot.run(config.DISCORD_TOKEN)
