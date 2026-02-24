import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ {bot.user} 봇이 준비되었습니다!")


@bot.command()
async def ping(ctx):
    """봇 응답 확인"""
    await ctx.send(f"🏓 Pong! ({round(bot.latency * 1000)}ms)")


bot.run(os.getenv("DISCORD_TOKEN"))
