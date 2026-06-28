import discord
from discord.ext import commands
from discord import app_commands
import os
import random
import sqlite3
from dotenv import load_dotenv

# ======================
# SETUP
# ======================
load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ======================
# DATABASE
# ======================
conn = sqlite3.connect("data.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    user_id INTEGER,
    guild_id INTEGER,
    count INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    channel_id INTEGER,
    message_id INTEGER
)
""")

conn.commit()

# ======================
# READY EVENT
# ======================
@bot.event
async def on_ready():
    print(f"NovaGuard gestartet als {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Slash Commands synchronisiert: {len(synced)}")
    except Exception as e:
        print(e)

# ======================
# ANALYTICS (MESSAGE TRACKING)
# ======================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    cursor.execute("""
    SELECT count FROM messages
    WHERE user_id=? AND guild_id=?
    """, (message.author.id, message.guild.id))

    result = cursor.fetchone()

    if result:
        cursor.execute("""
        UPDATE messages SET count=?
        WHERE user_id=? AND guild_id=?
        """, (result[0] + 1, message.author.id, message.guild.id))
    else:
        cursor.execute("""
        INSERT INTO messages VALUES (?, ?, 1)
        """, (message.author.id, message.guild.id))

    conn.commit()
    await bot.process_commands(message)

# ======================
# 📊 ANALYTICS COMMAND
# ======================
@bot.tree.command(name="top")
async def top(interaction: discord.Interaction):
    cursor.execute("""
    SELECT user_id, count FROM messages
    WHERE guild_id=?
    ORDER BY count DESC
    LIMIT 5
    """, (interaction.guild.id,))

    rows = cursor.fetchall()

    text = "📊 **Top User:**\n"
    for i, (user_id, count) in enumerate(rows):
        user = await bot.fetch_user(user_id)
        text += f"{i+1}. {user.name} - {count} Nachrichten\n"

    await interaction.response.send_message(text)

# ======================
# 🎁 GIVEAWAY SYSTEM
# ======================
@bot.tree.command(name="giveaway")
@app_commands.describe(prize="Was wird verlost?")
async def giveaway(interaction: discord.Interaction, prize: str):

    msg = await interaction.channel.send(
        f"🎁 GIVEAWAY 🎁\nPreis: **{prize}**\nReagiere mit 🎉 um teilzunehmen!"
    )

    await msg.add_reaction("🎉")

    cursor.execute("""
    INSERT INTO giveaways (guild_id, channel_id, message_id)
    VALUES (?, ?, ?)
    """, (interaction.guild.id, interaction.channel.id, msg.id))

    conn.commit()

    await interaction.response.send_message("Giveaway gestartet!", ephemeral=True)

# ======================
# 🎁 PICK WINNER
# ======================
@bot.tree.command(name="winner")
async def winner(interaction: discord.Interaction, message_id: str):

    msg = await interaction.channel.fetch_message(int(message_id))

    users = []
    for reaction in msg.reactions:
        if str(reaction.emoji) == "🎉":
            async for user in reaction.users():
                if not user.bot:
                    users.append(user)

    if not users:
        await interaction.response.send_message("Keine Teilnehmer 😢")
        return

    winner = random.choice(users)

    await interaction.response.send_message(f"🏆 Gewinner: {winner.mention}")

# ======================
# 💬 MODERATION
# ======================
@bot.tree.command(name="kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"{member} wurde gekickt. Grund: {reason}")

@bot.tree.command(name="ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"{member} wurde gebannt. Grund: {reason}")

# ======================
# 🔥 START
# ======================
bot.run(TOKEN)
