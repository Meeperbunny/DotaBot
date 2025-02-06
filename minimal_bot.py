import os
import csv
import tempfile
from datetime import datetime, timedelta
import zoneinfo

import discord
from discord.ext import commands

TOKEN = os.getenv("DOTABOT_APP_ID")

EMOJI_QUEUE  = "⚔️"
EMOJI_RANKED = "📈"
EMOJI_TURBO  = "⏩"
EMOJI_BC     = "🏆"
EMOJI_IH     = "🏠"
EMOJI_CANCEL = "❌"

DAILY_REWARD = 25

CACHE_DIR = os.path.join(tempfile.gettempdir(), "dotabotcache")
os.makedirs(CACHE_DIR, exist_ok=True)
CURRENCY_FILE = os.path.join(CACHE_DIR, "currency.csv")
ROLE_FILE = os.path.join(CACHE_DIR, "role_ids.csv")

LOCAL_ZONE = zoneinfo.ZoneInfo("America/Los_Angeles")

def load_currency_data():
    """
    Returns currency data in the format:
    {
      server_id: {
        user_id: {
          'currency': int,
          'last_claim_date': str (YYYY-MM-DD or 'none'),
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
    """
    Saves the currency data dictionary to CSV.
    """
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
    Returns a dictionary mapping server IDs to stored role IDs:
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
    """
    Saves the server-to-role mapping data to CSV.
    """
    with open(ROLE_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["server_id", "role_id"])
        writer.writeheader()
        for sid, rid in data.items():
            writer.writerow({"server_id": sid, "role_id": rid})

def get_now_local():
    """
    Returns the current datetime in LOCAL_ZONE.
    """
    return datetime.now(LOCAL_ZONE)

def get_today_str():
    """
    Returns today's date (YYYY-MM-DD) in LOCAL_ZONE.
    """
    return get_now_local().strftime("%Y-%m-%d")

def get_time_until_next_midnight():
    """
    Returns (hours, minutes) until the next local midnight.
    """
    now_local = get_now_local()
    next_midnight = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    diff = int((next_midnight - now_local).total_seconds())
    hours, rem = divmod(diff, 3600)
    minutes, _ = divmod(rem, 60)
    return hours, minutes

# Reaction threshold settings
reaction_thresholds = {
    "🏆": (6, "🏆 Battle Cup 🏆"),
    "⚔️": (6, "⚔️ Queue ⚔️"),
    "📈": (6, "📈 Ranked 📈"),
    "⏩": (6, "⏩ Turbo ⏩"),
    "🏠": (11, "🏠 Inhouse 🏠"),
}

# Create bot with all intents (be sure to adjust your intents in Discord Developer Portal if needed)
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} in {len(bot.guilds)} server(s).")
    for guild in bot.guilds:
        print(f"- {guild.name} (ID: {guild.id})")

@bot.event
async def on_guild_join(guild):
    """
    Automatically create or find the 'queue' role when the bot joins a new server.
    """
    roles_data = load_role_data()
    guild_id = str(guild.id)

    existing_role_id = roles_data.get(guild_id)
    role_obj = None

    if existing_role_id:
        role_obj = discord.utils.get(guild.roles, id=int(existing_role_id))

    # If the role doesn't exist, create a new one
    if not role_obj:
        role_obj = await guild.create_role(name="queue", mentionable=True)
        roles_data[guild_id] = str(role_obj.id)
        save_role_data(roles_data)

    print(f"'queue' role setup complete in guild: {guild.name} (ID: {guild.id}).")

@bot.event
async def on_reaction_add(reaction, user):
    """
    Automatically sends a new message if the threshold for reactions is met.
    """
    if reaction.message.author.id != bot.user.id or user.bot:
        return

    threshold, header_title = reaction_thresholds.get(str(reaction.emoji), (None, None))
    if threshold and reaction.count == threshold:
        await send_reply_msg(header_title, reaction)

async def send_reply_msg(header_msg, reaction):
    """
    Replies to the queue message with an embed listing participants once threshold is reached.
    """
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

async def send_queue_embed(ctx, title_template, emoji, color=discord.Color.purple()):
    """
    Sends a queue embed, reacts with the specified emoji, and mentions the @queue role.
    """
    roles_data = load_role_data()
    guild_id = str(ctx.guild.id)
    role_id = roles_data.get(guild_id)

    role_obj = None
    if role_id:
        role_obj = discord.utils.get(ctx.guild.roles, id=int(role_id))

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
    """
    Shows a concise list of available commands.
    """
    embed = discord.Embed(
        title="DotaBot Help",
        description=(
            "**Queue Commands**\n"
            "`!queue (!q, !u)` - Unranked queue\n"
            "`!ranked (!r)` - Ranked queue\n"
            "`!turbo (!t)` - Turbo queue\n"
            "`!battlecup (!bc)` - Battle Cup queue\n"
            "`!inhouse (!ih)` - Inhouse queue\n\n"
            "**Currency Commands**\n"
            "`!daily (!d)` - Claim daily rewards\n"
            "`!mmr` - See your points\n"
            "`!top` - Streak and point leaderboard\n\n"
            "**Role Command**\n"
            "`!role` - Assign yourself with the queue role\n"
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command()
async def role(ctx):
    """
    Create or find a 'queue' role, store its ID, and assign it to the user.
    """
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

@bot.command(aliases=["q", "u"])
async def queue(ctx):
    await send_queue_embed(ctx, "⚔️ Unranked Queue started by {sender} ⚔️", EMOJI_QUEUE)

@bot.command(aliases=["r"])
async def ranked(ctx):
    await send_queue_embed(ctx, "📈 Ranked Queue started by {sender} 📈", EMOJI_RANKED)

@bot.command(aliases=["t"])
async def turbo(ctx):
    await send_queue_embed(ctx, "⏩ Turbo Queue by {sender} ⏩", EMOJI_TURBO)

@bot.command(aliases=["bc"])
async def battlecup(ctx):
    await send_queue_embed(ctx, "🏆 Battle Cup Queue started by {sender} 🏆", EMOJI_BC)

@bot.command(aliases=["ih"])
async def inhouse(ctx):
    await send_queue_embed(ctx, "🏠 Inhouse started by {sender} 🏠", EMOJI_IH)

@bot.command(aliases=["d"])
async def daily(ctx):
    """
    Claim a daily reward, track streaks, and update currency.
    """
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

    # Check if daily is already claimed today
    if record["last_claim_date"] == today:
        hours, minutes = get_time_until_next_midnight()
        await ctx.send(
            f"{ctx.author.mention}, you've already claimed your daily. "
            f"Try again in **{hours}h {minutes}m**"
        )
        return

    # Update streak
    if record["last_claim_date"] != "none":
        prev = datetime.strptime(record["last_claim_date"], "%Y-%m-%d").date()
        curr = datetime.strptime(today, "%Y-%m-%d").date()
        if (curr - prev).days == 1:
            record["streak"] += 1
        else:
            record["streak"] = 1
    else:
        record["streak"] = 1

    # Update currency and save
    record["last_claim_date"] = today
    record["currency"] += DAILY_REWARD
    save_currency_data(data)

    await ctx.send(
        f"{ctx.author.mention}, daily reward claimed! "
        f"You now have **{record['currency']}🔸** ({record['streak']} day streak)"
    )

@bot.command()
async def mmr(ctx):
    """
    Shows the user's current currency/points.
    """
    guild_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)
    data = load_currency_data()
    record = data.get(guild_id, {}).get(user_id, {"currency": 0})

    await ctx.send(
        f"{ctx.author.mention}, you have **{record['currency']}🔸**"
    )

@bot.command()
async def top(ctx):
    """
    Shows a leaderboard of top 10 points and top 10 streaks.
    """
    guild_id = str(ctx.guild.id)
    data = load_currency_data()
    server_data = data.get(guild_id, {})

    if not server_data:
        await ctx.send("No data available for this server.")
        return

    sorted_by_points = sorted(server_data.items(), key=lambda x: x[1]["currency"], reverse=True)
    sorted_by_streak = sorted(server_data.items(), key=lambda x: x[1]["streak"], reverse=True)

    top_points = sorted_by_points[:10]
    top_streaks = sorted_by_streak[:10]

    # Generate points list
    points_desc = ""
    for i, (user_id, info) in enumerate(top_points, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        points_desc += f"{i}. {name} — **{info['currency']}🔸**\n"

    # Generate streak list
    streak_desc = ""
    for i, (user_id, info) in enumerate(top_streaks, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        streak_desc += f"{i}. {name} — **{info['streak']}🔥**\n"

    embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())
    if points_desc:
        embed.add_field(name="Top Points", value=points_desc, inline=False)
    if streak_desc:
        embed.add_field(name="Top Streaks", value=streak_desc, inline=False)

    await ctx.send(embed=embed)

# Optional: If you'd like to keep this command but exclude it from !help,
# simply don't reference it in the help text.
@bot.command()
async def trivia(ctx):
    """
    Placeholder command (unreferenced in !help).
    """
    await ctx.send("Trivia is currently unimplemented.")

# Entry point for running the bot
if __name__ == "__main__":
    bot.run(TOKEN)
