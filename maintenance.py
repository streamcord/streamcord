import discord, asyncio
from utils import settings
import logging

c = discord.Client()
logging.basicConfig(level=logging.INFO, format='%(levelname)s/%(module)s @ %(asctime)s: %(message)s', datefmt='%I:%M:%S %p')

@c.event
async def on_ready():
    await c.change_presence(status=discord.Status.dnd, game=discord.Game(name="Maintenance Mode"))

@c.event
async def on_message(message):
    if message.content.lower().startswith("twitch"):
        await c.send_message(message.channel, "I'm currently in maintenance mode, and will be back online shortly. Join the support Discord at discord.me/konomi for updates.")

c.run(settings.TOKEN)
