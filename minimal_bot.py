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

def load_role_data():
    """ { server_id: role_id } """
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

async def get_or_create_queue_role(guild):
    """Ensures the 'queue' role exists in the server, creates it if missing, and updates storage."""
    roles_data = load_role_data()
    guild_id = str(guild.id)

    existing_role_id = roles_data.get(guild_id)
    role_obj = discord.utils.get(guild.roles, id=int(existing_role_id)) if existing_role_id else None

    if not role_obj:
        role_obj = await guild.create_role(name="queue", mentionable=True)
        roles_data[guild_id] = str(role_obj.id)
        save_role_data(roles_data)

    return role_obj

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} in {len(bot.guilds)} server(s).")
    for guild in bot.guilds:
        await get_or_create_queue_role(guild)

@bot.event
async def on_guild_join(guild):
    """Automatically create a 'queue' role when joining a new server."""
    await get_or_create_queue_role(guild)

async def send_queue_embed(ctx, title_template, emoji):
    """Sends a queue embed and pings the @queue role."""
    guild_id = str(ctx.guild.id)
    roles_data = load_role_data()
    role_id = roles_data.get(guild_id)
    role_obj = discord.utils.get(ctx.guild.roles, id=int(role_id)) if role_id else None

    sender = ctx.author.display_name
    embed = discord.Embed(
        title=title_template.format(sender=sender),
        description="React to join",
        color=discord.Color.purple()
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
            "!role           - Get the queue role\n"
            "!q !queue       - Start an Unranked queue\n"
            "!r !ranked      - Start a Ranked queue\n"
            "!t !turbo       - Start a Turbo queue\n"
            "!bc !battlecup  - Start a Battle Cup queue\n"
            "!ih !inhouse    - Start an Inhouse queue\n"
            "!d !daily       - Claim your daily reward\n"
            "!mmr            - Check your points\n"
            "!top            - Show top point/streak holders\n"
        ),
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command()
async def role(ctx):
    """Assign the 'queue' role to the user."""
    role_obj = await get_or_create_queue_role(ctx.guild)
    await ctx.author.add_roles(role_obj)
    await ctx.send(f"{ctx.author.mention} was assigned to {role_obj.mention}.")

@bot.command(aliases=["q"])
async def queue(ctx):
    await send_queue_embed(ctx, "⚔️ Queue by {sender}", EMOJI_QUEUE)

@bot.command(aliases=["r"])
async def ranked(ctx):
    await send_queue_embed(ctx, "📈 Ranked Queue by {sender}", EMOJI_RANKED)

@bot.command(aliases=["t"])
async def turbo(ctx):
    await send_queue_embed(ctx, "⏩ Turbo by {sender}", EMOJI_TURBO)

@bot.command(aliases=["bc"])
async def battlecup(ctx):
    await send_queue_embed(ctx, "🏆 Battle Cup by {sender}", EMOJI_BC)

@bot.command(aliases=["ih"])
async def inhouse(ctx):
    await send_queue_embed(ctx, "🏠 Inhouse by {sender}", EMOJI_IH)

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

    if not server_data:
        await ctx.send("No data available for this server.")
        return

    sorted_by_points = sorted(server_data.items(), key=lambda x: x[1]["currency"], reverse=True)
    sorted_by_streak = sorted(server_data.items(), key=lambda x: x[1]["streak"], reverse=True)

    top_points = sorted_by_points[:10]
    top_streaks = sorted_by_streak[:10]

    points_desc = ""
    for i, (user_id, info) in enumerate(top_points, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        points_desc += f"{i}. {name} — **{info['currency']}🔸**\n"

    streak_desc = ""
    for i, (user_id, info) in enumerate(top_streaks, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        streak_desc += f"{i}. {name} — **{info['streak']} 🔥**\n"

    embed = discord.Embed(title="Leaderboard", color=discord.Color.gold())

    if points_desc:
        embed.add_field(name="Top Point Holders", value=points_desc, inline=False)
    if streak_desc:
        embed.add_field(name="Top Streak Holders", value=streak_desc, inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def trivia(ctx):
    await ctx.send("Trivia is currently unimplemented.")

if __name__ == "__main__":
    bot.run(TOKEN)
