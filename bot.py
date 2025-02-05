import os
import csv
import json
import random
import requests
import tempfile
import shutil
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

# =======================
# Configuration Constants
# =======================

# Reads the token from an environment variable, falling back to a placeholder string
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

GUILD_ID = os.getenv("DISCORD_GUILD_ID", "YOUR_GUILD_ID_HERE")

# Role IDs (example IDs)
ROLE_DEFAULT_ID = 1078825365306355712
ROLE_IR_ID = 1275633243605172355
ROLE_DL_ID = 1278505142483812404

# Emoji Constants
EMOJI_QUEUE   = "⚔️"
EMOJI_RANKED  = "📈"
EMOJI_IR      = "<:immortal:1156278341096194098>"
EMOJI_MID     = "💃"
EMOJI_TURBO   = "⏩"
EMOJI_BC      = "🏆"
EMOJI_IH      = "🏠"
EMOJI_DL      = "🔒"
EMOJI_CANCEL  = "❌"

# Daily replies
EMOJI_TORMIE  = "<:tormie:1166072711982878842>"

# Match Trivia Emojis
GREEN_CIRCLE = "🟢"  # Radiant
RED_CIRCLE   = "🔴"  # Dire
DOUBLE_DOWN  = "💰"  # double down

# Over/Under Emojis
EMOJI_OVER   = "⬆️"  # higher guess
EMOJI_UNDER  = "⬇️"  # lower guess

# Daily reward settings
DAILY_REWARD = 25
DAILY_INTERVAL = timedelta(hours=23)

# -----------------------
# File Cache Directory in OS Temp
# -----------------------
CACHE_DIR = os.path.join(tempfile.gettempdir(), "dotabot-cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CURRENCY_FILE = os.path.join(CACHE_DIR, "currency.csv")
HERO_STATS_FILE = os.path.join(CACHE_DIR, "heroStats.json")

# If heroStats.json not found, try local or fetch from the API
if not os.path.exists(HERO_STATS_FILE):
    local_hero_stats = "heroStats.json"
    if os.path.exists(local_hero_stats):
        shutil.copy(local_hero_stats, HERO_STATS_FILE)
    else:
        print("heroStats.json not found locally. Fetching from OpenDota API...")
        try:
            resp = requests.get("https://api.opendota.com/api/heroStats", timeout=10)
            if resp.status_code == 200:
                with open(HERO_STATS_FILE, "w", encoding="utf-8") as f:
                    json.dump(resp.json(), f)
            else:
                raise Exception(f"API returned status code {resp.status_code}")
        except Exception as e:
            raise FileNotFoundError("heroStats.json not found, and API call failed: " + str(e))

# =======================
# Load Hero Data
# =======================
try:
    with open(HERO_STATS_FILE, "r", encoding="utf-8") as f:
        heroes_data = json.load(f)
except Exception as e:
    print("Error loading heroStats.json:", e)
    heroes_data = []

# Map hero ID -> localized_name
hero_dict = {h["id"]: h.get("localized_name", f"HeroID_{h['id']}") for h in heroes_data}

# =======================
# Public Matches (Trivias)
# =======================
match_cache = []
used_match_ids = set()

def fetch_matches():
    """Fetch public matches from OpenDota and store only 5v5 matches in match_cache."""
    global match_cache
    try:
        url = "https://www.opendota.com/api/publicMatches"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            all_matches = resp.json()
            filtered = []
            for m in all_matches:
                if (
                    "match_id" in m and "radiant_win" in m and "duration" in m
                    and "radiant_team" in m and "dire_team" in m
                    and isinstance(m["radiant_team"], list)
                    and isinstance(m["dire_team"], list)
                    and len(m["radiant_team"]) == 5
                    and len(m["dire_team"]) == 5
                ):
                    filtered.append(m)
            match_cache = filtered
    except Exception as e:
        print("Error fetching matches:", e)

def get_next_match():
    """Return a 5v5 match not used yet. If needed, fetch more. Keep track of used match_ids."""
    global match_cache, used_match_ids
    if len(match_cache) < 3:
        fetch_matches()
    while match_cache and match_cache[0]["match_id"] in used_match_ids:
        match_cache.pop(0)
    if match_cache:
        m = match_cache.pop(0)
        used_match_ids.add(m["match_id"])
        return m
    return None

# =======================
# CSV Data (MMR)
# =======================
def load_currency_data():
    data = {}
    if os.path.exists(CURRENCY_FILE):
        with open(CURRENCY_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row["user_id"]
                data[uid] = {
                    "currency": int(row["currency"]),
                    "last_daily": row["last_daily"]
                }
    return data

def save_currency_data(data):
    with open(CURRENCY_FILE, "w", newline="") as f:
        fieldnames = ["user_id", "currency", "last_daily"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for uid, record in data.items():
            writer.writerow({
                "user_id": uid,
                "currency": record["currency"],
                "last_daily": record["last_daily"]
            })

# =======================
# Helper / Utility
# =======================
def get_sender_name(ctx):
    return ctx.author.nick if ctx.author.nick else ctx.author.name

async def send_queue_embed(ctx, title_template, emoji, role_obj, color=discord.Color.purple()):
    sender = get_sender_name(ctx)
    embed_title = title_template.format(sender=sender)
    embed = discord.Embed(title=embed_title, description="React below to join", color=color)
    msg = await ctx.send(embed=embed)
    await msg.add_reaction(emoji)
    await msg.add_reaction(EMOJI_CANCEL)
    if role_obj:
        await ctx.send(role_obj.mention)

async def send_reply_msg(header_msg, reaction):
    embed = discord.Embed(title=header_msg, color=discord.Color.teal())
    participants = []
    async for user in reaction.users():
        if not user.bot:
            participants.append(user.name)
    if participants:
        embed.add_field(name="Participants:", value=", ".join(participants), inline=True)
    else:
        embed.add_field(name="Participants:", value="None", inline=True)
    await reaction.message.reply(embed=embed)

reaction_thresholds = {
    "🏆": (6, "🏆 Battle Cup 🏆"),
    "⚔️": (6, "⚔️ Queue ⚔️"),
    "📈": (6, "📈 Ranked 📈"),
    "💃": (3, "💃 1v1 Mid 💃"),
    "⏩": (6, "⏩ Turbo ⏩"),
    "🏠": (11, "🏠 Inhouse 🏠"),
    "🔒": (7, "🔒 Deadlock 🔒")
}

# =======================
# Bot Initialization
# =======================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# =======================
# Events
# =======================
@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("Guild not found. Shutting down.")
        await bot.close()
        return
    print(f"Connected to guild: {guild.name} (id: {guild.id})")
    print(f"Logged in as: {bot.user}")

@bot.event
async def on_reaction_add(reaction, user):
    if reaction.message.author.id != bot.user.id or user.bot:
        return

    threshold = None
    header_title = None

    # Check for Immortal custom emoji
    if isinstance(reaction.emoji, discord.PartialEmoji) and (reaction.emoji.id == 1156278341096194098):
        threshold, header_title = 6, "<:immortal:1156278341096194098> Immortal Ranked <:immortal:1156278341096194098>"
    elif isinstance(reaction.emoji, str) and reaction.emoji in reaction_thresholds:
        threshold, header_title = reaction_thresholds[reaction.emoji]

    if threshold is not None and reaction.count == threshold:
        await send_reply_msg(header_title, reaction)

# =======================
# Commands
# =======================
@bot.command(aliases=['help'])
async def H(ctx):
    embed = discord.Embed(
        title="Dota Queue Bot Commands",
        description=(
            "!BC !battlecup      - Dota battlecup\n"
            "!D !daily !d        - Claim your daily 25 MMR\n"
            "!mmr !MMR           - Check your MMR\n"
            "!top !topmmr        - Show the top MMR holders\n"
            "!trivia !TRIVIA     - 50% match trivia, 50% hero Over/Under\n"
            "!DL !deadlock !dl   - Deadlock queue\n"
            "!IH !inhouse !ih    - Dota Inhouse\n"
            "!IR !immortalranked !ir - Dota immortal ranked Queue\n"
            "!M  !mid !m         - 1v1 mid\n"
            "!Q  !queue !q       - Dota queue\n"
            "!R  !ranked !r      - Dota ranked queue\n"
            "!T  !turbo !t       - Dota Turbo"
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(aliases=['queue','q'])
async def Q(ctx):
    role = discord.utils.get(ctx.guild.roles, id=ROLE_DEFAULT_ID)
    await send_queue_embed(ctx, "⚔️ Queue started by {sender} ⚔️", EMOJI_QUEUE, role)

@bot.command(aliases=['ranked','r'])
async def R(ctx):
    role = discord.utils.get(ctx.guild.roles, id=ROLE_DEFAULT_ID)
    await send_queue_embed(ctx, "📈 Ranked Queue started by {sender} 📈", EMOJI_RANKED, role)

@bot.command(aliases=['immortalranked','ir'])
async def IR(ctx):
    role = discord.utils.get(ctx.guild.roles, id=ROLE_IR_ID)
    await send_queue_embed(ctx, "<:immortal:1156278341096194098> Immortal Ranked Queue started by {sender} <:immortal:1156278341096194098>", EMOJI_IR, role)

@bot.command(aliases=['mid','m'])
async def M(ctx):
    role = discord.utils.get(ctx.guild.roles, id=ROLE_DEFAULT_ID)
    await send_queue_embed(ctx, "💃 1v1 Mid started by {sender} 💃", EMOJI_MID, role)

@bot.command(aliases=['turbo','t'])
async def T(ctx):
    role = discord.utils.get(ctx.guild.roles, id=ROLE_DEFAULT_ID)
    await send_queue_embed(ctx, "⏩ Turbo started by {sender} ⏩", EMOJI_TURBO, role)

@bot.command(aliases=["battlecup","bc"])
async def BC(ctx):
    role = discord.utils.get(ctx.guild.roles, id=ROLE_DEFAULT_ID)
    await send_queue_embed(ctx, "🏆 Battle Cup started by {sender} 🏆", EMOJI_BC, role)

@bot.command(aliases=["inhouse","ih"])
async def IH(ctx):
    role = discord.utils.get(ctx.guild.roles, id=ROLE_DEFAULT_ID)
    await send_queue_embed(ctx, "🏠 Inhouse Started By {sender} 🏠", EMOJI_IH, role)

@bot.command(aliases=['deadlock','dl'])
async def DL(ctx):
    role = discord.utils.get(ctx.guild.roles, id=ROLE_DL_ID)
    await send_queue_embed(ctx, "🔒 Deadlock Queue started by {sender} 🔒", EMOJI_DL, role)

@bot.command(aliases=['daily','d'])
async def D(ctx):
    """
    Claim your daily reward of 25 MMR.
    The user can only claim once every 23 hours.
    Sends a :tormie: emoji on success.
    """
    user_id = str(ctx.author.id)
    data = load_currency_data()
    record = data.get(user_id, {"currency": 0, "last_daily": "none"})

    now = datetime.now(timezone.utc)
    eligible = False

    if record["last_daily"] == "none":
        eligible = True
    else:
        try:
            last_claim = datetime.fromisoformat(record["last_daily"])
            if last_claim.tzinfo is None:
                last_claim = last_claim.replace(tzinfo=timezone.utc)
        except:
            eligible = True
        else:
            if now - last_claim >= DAILY_INTERVAL:
                eligible = True

    if eligible:
        record["currency"] += DAILY_REWARD
        record["last_daily"] = now.isoformat()
        data[user_id] = record
        save_currency_data(data)
        # Use the Tormie emoji in the success message
        await ctx.send(
            f"{ctx.author.mention}, daily reward claimed! Now you have **{record['currency']} MMR** {EMOJI_TORMIE}"
        )
    else:
        if last_claim.tzinfo is None:
            last_claim = last_claim.replace(tzinfo=timezone.utc)
        time_remaining = DAILY_INTERVAL - (now - last_claim)
        hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(
            f"{ctx.author.mention}, you already claimed your daily reward. "
            f"Try again in **{hours}h {minutes}m {seconds}s**."
        )

@bot.command(aliases=['mmr'])
async def MMR(ctx):
    user_id = str(ctx.author.id)
    data = load_currency_data()
    current = data.get(user_id, {"currency": 0})["currency"]
    await ctx.send(f"{ctx.author.mention}, you have **{current} MMR** {EMOJI_TORMIE}")

@bot.command(aliases=['topmmr','top'])
async def TOP(ctx):
    data = load_currency_data()
    sorted_data = sorted(data.items(), key=lambda x: x[1]["currency"], reverse=True)
    top_ten = sorted_data[:10]
    guild = ctx.guild

    desc = ""
    for i, (u_id, info) in enumerate(top_ten, start=1):
        member = guild.get_member(int(u_id))
        name = member.display_name if member else f"User ID {u_id}"
        desc += f"**{i}. {name}** — {info['currency']} MMR\n"

    embed = discord.Embed(title="Top MMR Holders", description=desc, color=discord.Color.gold())
    await ctx.send(embed=embed)

# =======================
# Over/Under Trivia
# =======================
RELEVANT_STATS = [
    "base_health", "base_mana",
    "str_gain", "agi_gain", "int_gain",
    "base_armor",
    "attack_range", "attack_rate", "move_speed"
]

async def do_hero_over_under_trivia(ctx):
    """
    1) Random hero from heroStats.
    2) Random stat from RELEVANT_STATS.
    3) Multiply real stat by ~0.8..1.2 => displayed_value
    4) Ask Over (⬆️) or Under (⬇️), plus Double Down (💰).
    5) ±5 or ±10 MMR based on correctness + double down
    6) Show hero image in the embed
    """
    valid_heroes = [h for h in heroes_data if any(s in h for s in RELEVANT_STATS)]
    if not valid_heroes:
        await ctx.send("No hero data available for Over/Under.")
        return

    hero = random.choice(valid_heroes)
    hero_name = hero.get("localized_name", "Unknown Hero")

    # Attempt to get the hero's image
    hero_img = None
    if "img" in hero:
        hero_img = "https://cdn.cloudflare.steamstatic.com" + hero["img"]

    possible_stats = [s for s in RELEVANT_STATS if s in hero]
    if not possible_stats:
        await ctx.send("No valid stats found for this hero.")
        return

    chosen_stat = random.choice(possible_stats)
    real_value = hero[chosen_stat]
    if not isinstance(real_value, (int, float)):
        await ctx.send("Picked a non-numeric stat. Try again.")
        return

    factor = random.uniform(0.8, 1.2)
    displayed_value = round(factor * real_value, 1)

    embed = discord.Embed(title="Hero Over/Under Trivia", color=discord.Color.blue())
    embed.description = (
        f"**Hero**: {hero_name}\n"
        f"**Stat**: {chosen_stat}\n\n"
        f"We show: **{displayed_value}**.\n\n"
        "Is the real value Over or Under that number?"
    )
    if hero_img:
        embed.set_image(url=hero_img)

    embed.set_footer(text=(
        f"React {EMOJI_OVER} if real stat is OVER.\n"
        f"React {EMOJI_UNDER} if it's UNDER.\n"
        f"React {DOUBLE_DOWN} to double down (±10). Otherwise ±5."
    ))

    trivia_msg = await ctx.send(embed=embed)
    await trivia_msg.add_reaction(EMOJI_OVER)
    await trivia_msg.add_reaction(EMOJI_UNDER)
    await trivia_msg.add_reaction(DOUBLE_DOWN)

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == trivia_msg.id
            and str(reaction.emoji) in [EMOJI_OVER, EMOJI_UNDER]
        )

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
    except:
        await ctx.send("You took too long to respond.")
        return

    user_guess_over = (str(reaction.emoji) == EMOJI_OVER)

    double_down_triggered = False
    updated_msg = await ctx.fetch_message(trivia_msg.id)
    for r in updated_msg.reactions:
        if str(r.emoji) == DOUBLE_DOWN:
            async for reactor in r.users():
                if reactor == ctx.author:
                    double_down_triggered = True
                    break

    real_is_over = (real_value > displayed_value)
    if user_guess_over == real_is_over:
        change = 10 if double_down_triggered else 5
        result_text = f"Correct! You gain {change} MMR."
    else:
        change = -10 if double_down_triggered else -5
        result_text = f"Incorrect! You lose {abs(change)} MMR."

    # Update MMR
    user_id = str(ctx.author.id)
    data = load_currency_data()
    record = data.get(user_id, {"currency": 0, "last_daily": "none"})
    record["currency"] += change
    data[user_id] = record
    save_currency_data(data)

    over_or_under = "over" if real_value > displayed_value else "under"
    await ctx.send(
        f"{ctx.author.mention} {result_text}\n"
        f"The real value is **{real_value}**, which is **{over_or_under}** {displayed_value}.\n"
        f"Your new MMR: **{record['currency']}**."
    )

# =======================
# Match Trivia (No Images)
# =======================
async def do_match_trivia(ctx):
    """
    5v5 match from public matches.
    🟢 => Radiant, 🔴 => Dire, 💰 => Double Down
    Correct => +5 or +10, Incorrect => -5 or -10
    (No hero images, only names.)
    """
    match = get_next_match()
    if not match:
        await ctx.send("No matches available right now. Try again later.")
        return

    rad_ids = match["radiant_team"]
    dire_ids = match["dire_team"]
    radiant_heroes = [hero_dict.get(h, f"HeroID {h}") for h in rad_ids]
    dire_heroes = [hero_dict.get(h, f"HeroID {h}") for h in dire_ids]
    mins = match["duration"] // 60
    secs = match["duration"] % 60

    embed = discord.Embed(title="Match Trivia", color=discord.Color.blue())
    embed.add_field(name="Radiant Team", value=", ".join(radiant_heroes), inline=False)
    embed.add_field(name="Dire Team", value=", ".join(dire_heroes), inline=False)
    embed.add_field(name="Duration", value=f"{mins}m {secs}s", inline=False)
    embed.set_footer(text=(
        f"React {GREEN_CIRCLE} if Radiant won, {RED_CIRCLE} if Dire won.\n"
        f"React {DOUBLE_DOWN} to double down (±10) otherwise ±5."
    ))

    trivia_msg = await ctx.send(embed=embed)
    await trivia_msg.add_reaction(GREEN_CIRCLE)
    await trivia_msg.add_reaction(RED_CIRCLE)
    await trivia_msg.add_reaction(DOUBLE_DOWN)

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == trivia_msg.id
            and str(reaction.emoji) in [GREEN_CIRCLE, RED_CIRCLE]
        )

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
    except:
        await ctx.send("You took too long to respond.")
        return

    guess_radiant = (str(reaction.emoji) == GREEN_CIRCLE)
    updated_msg = await ctx.fetch_message(trivia_msg.id)
    double_down_triggered = False
    for r in updated_msg.reactions:
        if str(r.emoji) == DOUBLE_DOWN:
            async for reactor in r.users():
                if reactor == ctx.author:
                    double_down_triggered = True
                    break

    actual_radiant_win = match["radiant_win"]
    if guess_radiant == actual_radiant_win:
        points = 10 if double_down_triggered else 5
        result_text = f"Correct! You gain {points} MMR."
    else:
        points = -10 if double_down_triggered else -5
        result_text = f"Incorrect! You lose {abs(points)} MMR."

    user_id = str(ctx.author.id)
    data = load_currency_data()
    record = data.get(user_id, {"currency": 0, "last_daily": "none"})
    record["currency"] += points
    data[user_id] = record
    save_currency_data(data)

    winner_str = "Radiant" if match["radiant_win"] else "Dire"
    await ctx.send(
        f"{ctx.author.mention} {result_text}\n"
        f"The actual winner was **{winner_str}**.\n"
        f"Your new MMR: **{record['currency']}**."
    )

@bot.command(aliases=['TRIVIA'])
async def trivia(ctx):
    """
    50% chance for Over/Under hero stat trivia
    50% chance for match-based trivia (no hero images).
    """
    if random.random() < 0.5:
        await do_hero_over_under_trivia(ctx)
    else:
        await do_match_trivia(ctx)

# =======================
# Run the Bot
# =======================
if __name__ == "__main__":
    # MAKE SURE to set your environment variable or replace "YOUR_BOT_TOKEN_HERE"
    bot.run(TOKEN)
