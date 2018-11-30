from discord.ext import commands
import discord, asyncio
import websockets

class Streamlabs:
    def __init__(self, bot):
        self.bot = bot

def setup(bot):
    bot.add_cog(Streamlabs(bot))
