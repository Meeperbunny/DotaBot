import os
import csv
import tempfile
from datetime import datetime, timedelta
import zoneinfo

import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

EMOJI_QUEUE  = "⚔️"
EMOJI_RANKED = "📈"
EMOJI_TURBO  = "⏩"
EMOJI_BC     = "🏆"
EMOJI_IH     = "🏠"
EMOJI_CANCEL = "❌"

DAILY_REWARD = 25

CACHE_DIR = os.path.join(tempfile.gettempdir(), "dotabot-cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CURRENCY_FILE = os.path.join(CACHE_DIR, "currency.csv")
ROLE_FILE = os.path.join(CACHE_DIR, "role_ids.csv")

LOCAL_ZONE = zoneinfo.ZoneInfo("America/Los_Angeles")

def load_currency_data():
    """
    {
      server_id: {
        user_id: {
          'currency': int,
          'last_claim_date': 'YYYY-MM-DD' or 'none',
          'streak': int
        }
      }
    }
    """
    data = {}
    if os.path.exists(CURRENCY_FILE):
        with open(CURRENCY_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row["server_id"]
                uid = row["user_id"]
                if sid not in data:
                    data[sid] = {}
                data[sid][uid] = {
                    "currency": int(row["currency"]),
                    "last_claim_date": row["last_claim_date"],
                    "streak": int(row["streak"])
                }
    return data

def save_currency_data(data):
    with open(CURRENCY_FILE, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["server_id", "user_id", "currency", "last_claim_date", "streak"]
        )
        writer.writeheader()
        for server_id, user_dict in data.items():
            for user_id, record in user_dict.items():
                writer.writerow({
                    "server_id": server_id,
                    "user_id": user_id,
                    "currency": record["currency"],
                    "last_claim_date": record["last_claim_date"],
                    "streak": record["streak"]
                })

def load_role_data():
    """
    { server_id: role_id }
    """
    data = {}
    if os.path.exists(ROLE_FILE):
        with open(ROLE_FILE, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data[row["server_id"]] = row["role_id"]
    return data

def save_role_data(data):
    with open(ROLE_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["server_id", "role_id"])
        writer.writeheader()
        for sid, rid in data.items():
            writer.writerow({"server_id": sid, "role_id": rid})

def get_now_local():
    return datetime.now(LOCAL_ZONE)

def get_today_str():
    return get_now_local().strftime("%Y-%m-%d")

def get_time_until_next_midnight():
    now_local = get_now_local()
    next_midnight = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    diff = int((next_midnight - now_local).total_seconds())
    hours, rem = divmod(diff, 3600)
    minutes, _ = divmod(rem, 60)
    return hours, minutes

reaction_thresholds = {
    "🏆": (6, "🏆 Battle Cup 🏆"),
    "⚔️": (6, "⚔️ Queue ⚔️"),
    "📈": (6, "📈 Ranked 📈"),
    "⏩": (6, "⏩ Turbo ⏩"),
    "🏠": (11, "🏠 Inhouse 🏠"),
}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} in {len(bot.guilds)} server(s).")
    for guild in bot.guilds:
        print(f"- {guild.name} (ID: {guild.id})")

@bot.event
async def on_reaction_add(reaction, user):
    if reaction.message.author.id != bot.user.id or user.bot:
        return
    threshold, header_title = reaction_thresholds.get(str(reaction.emoji), (None, None))
    if threshold and reaction.count == threshold:
        await send_reply_msg(header_title, reaction)

async def send_reply_msg(header_msg, reaction):
    embed = discord.Embed(title=header_msg, color=discord.Color.teal())
    participants = []
    async for usr in reaction.users():
        if not usr.bot:
            participants.append(usr.name)
    if participants:
        embed.add_field(name="Participants", value=", ".join(participants), inline=True)
    else:
        embed.add_field(name="Participants", value="None", inline=True)
    await reaction.message.reply(embed=embed)

async def send_queue_embed(ctx, title_template, emoji, role_obj, color=discord.Color.purple()):
    sender = ctx.author.display_name
    embed = discord.Embed(
        title=title_template.format(sender=sender),
        description="React to join",
        color=color
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction(emoji)
    await msg.add_reaction(EMOJI_CANCEL)
    if role_obj:
        await ctx.send(role_obj.mention)

@bot.command(aliases=["h"])
async def help(ctx):
    embed = discord.Embed(
        title="DotaBot Commands",
        description=(
            "!bc !battlecup  - Start a Battle Cup\n"
            "!d !daily       - Claim your daily reward\n"
            "!mmr            - Check your points\n"
            "!top            - Show top point holders\n"
            "!trivia         - Unimplemented trivia\n"
            "!ih !inhouse    - Start an Inhouse queue\n"
            "!q !queue       - Start a regular queue\n"
            "!r !ranked      - Start a Ranked queue\n"
            "!t !turbo       - Start a Turbo queue"
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command()
async def role(ctx):
    """Create or find a 'queue' role, store ID, and assign it to the user."""
    guild_id = str(ctx.guild.id)
    roles_data = load_role_data()
    existing_role_id = roles_data.get(guild_id)

    role_obj = None
    if existing_role_id:
        role_obj = discord.utils.get(ctx.guild.roles, id=int(existing_role_id))

    # Create if not found
    if not role_obj:
        role_obj = await ctx.guild.create_role(name="queue", mentionable=True)
        roles_data[guild_id] = str(role_obj.id)
        save_role_data(roles_data)

    await ctx.author.add_roles(role_obj)
    await ctx.send(f"{ctx.author.mention} was assigned to {role_obj.mention}.")

@bot.command(aliases=["q"])
async def queue(ctx):
    guild_id = str(ctx.guild.id)
    roles_data = load_role_data()
    role_id = roles_data.get(guild_id)
    role_obj = discord.utils.get(ctx.guild.roles, id=int(role_id)) if role_id else None
    await send_queue_embed(ctx, "⚔️ Queue by {sender}", EMOJI_QUEUE, role_obj)

@bot.command(aliases=["r"])
async def ranked(ctx):
    guild_id = str(ctx.guild.id)
    roles_data = load_role_data()
    role_id = roles_data.get(guild_id)
    role_obj = discord.utils.get(ctx.guild.roles, id=int(role_id)) if role_id else None
    await send_queue_embed(ctx, "📈 Ranked Queue by {sender}", EMOJI_RANKED, role_obj)

@bot.command(aliases=["t"])
async def turbo(ctx):
    guild_id = str(ctx.guild.id)
    roles_data = load_role_data()
    role_id = roles_data.get(guild_id)
    role_obj = discord.utils.get(ctx.guild.roles, id=int(role_id)) if role_id else None
    await send_queue_embed(ctx, "⏩ Turbo by {sender}", EMOJI_TURBO, role_obj)

@bot.command(aliases=["bc"])
async def battlecup(ctx):
    guild_id = str(ctx.guild.id)
    roles_data = load_role_data()
    role_id = roles_data.get(guild_id)
    role_obj = discord.utils.get(ctx.guild.roles, id=int(role_id)) if role_id else None
    await send_queue_embed(ctx, "🏆 Battle Cup by {sender}", EMOJI_BC, role_obj)

@bot.command(aliases=["ih"])
async def inhouse(ctx):
    guild_id = str(ctx.guild.id)
    roles_data = load_role_data()
    role_id = roles_data.get(guild_id)
    role_obj = discord.utils.get(ctx.guild.roles, id=int(role_id)) if role_id else None
    await send_queue_embed(ctx, "🏠 Inhouse by {sender}", EMOJI_IH, role_obj)

@bot.command(aliases=["d"])
async def daily(ctx):
    guild_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)
    data = load_currency_data()

    if guild_id not in data:
        data[guild_id] = {}
    if user_id not in data[guild_id]:
        data[guild_id][user_id] = {
            "currency": 0,
            "last_claim_date": "none",
            "streak": 0
        }

    record = data[guild_id][user_id]
    today = get_today_str()

    if record["last_claim_date"] == today:
        hours, minutes = get_time_until_next_midnight()
        await ctx.send(
            f"{ctx.author.mention}, you've already claimed your daily. "
            f"Try again in {hours} hours {minutes} minutes."
        )
        return

    if record["last_claim_date"] != "none":
        prev = datetime.strptime(record["last_claim_date"], "%Y-%m-%d").date()
        curr = datetime.strptime(today, "%Y-%m-%d").date()
        if (curr - prev).days == 1:
            record["streak"] += 1
        else:
            record["streak"] = 1
    else:
        record["streak"] = 1

    record["last_claim_date"] = today
    record["currency"] += DAILY_REWARD
    save_currency_data(data)

    await ctx.send(
        f"{ctx.author.mention}, daily reward claimed! "
        f"You now have **{record['currency']}🔸**. Streak: {record['streak']} days in a row."
    )

@bot.command()
async def mmr(ctx):
    guild_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)
    data = load_currency_data()
    record = data.get(guild_id, {}).get(user_id, {"currency": 0})
    await ctx.send(
        f"{ctx.author.mention}, you have **{record['currency']}🔸**."
    )

@bot.command()
async def top(ctx):
    guild_id = str(ctx.guild.id)
    data = load_currency_data()
    server_data = data.get(guild_id, {})
    sorted_data = sorted(server_data.items(), key=lambda x: x[1]["currency"], reverse=True)
    top_ten = sorted_data[:10]
    desc = ""
    for i, (user_id, info) in enumerate(top_ten, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        desc += f"{i}. {name} — **{info['currency']}🔸**\n"

    embed = discord.Embed(title="Top Point Holders", description=desc, color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command()
async def trivia(ctx):
    await ctx.send("Trivia is currently unimplemented.")

if __name__ == "__main__":
    bot.run(TOKEN)
