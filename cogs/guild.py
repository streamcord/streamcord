from utils import settings, functions, lang, http
from discord.ext import commands
import logging, traceback
import asyncio, aiohttp
import requests
import discord

class SubMode(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(no_pm=True)
    async def sub_role(self, ctx):
        pass
