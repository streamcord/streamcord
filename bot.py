from discord.ext import commands
import discord, asyncio
import logging, traceback
import json
import os, sys
import time

from utils import presence
from utils import settings

logging.basicConfig(level=logging.INFO, format='%(levelname)s/%(module)s @ %(asctime)s: %(message)s', datefmt='%I:%M:%S %p')
log = logging.getLogger("bot.core")

modules = ["mod.general", "mod.users", "mod.games", "mod.streams", "mod.audio", "mod.notifs", "mod.stats", "mod.dev", "mod.clips"]

bot = commands.AutoShardedBot(command_prefix=["twitch ", "Twitch "])
bot.remove_command('help')
bot.notifs = json.loads(open(os.path.join(os.getcwd(), 'data', 'notifs.json')).read())
bot.cmds = 0
bot.ratelimits = {"twitch": 0, "fortnite": 0, "rocketleague": 0, "pubg": 0}
bot.vc = {}
bot.uptime = 0

if __name__ == "__main__":
    for m in modules:
        try:
            bot.load_extension(m)
        except:
            log.error("Failed to load " + m)
            log.error(traceback.format_exc())
        else:
            log.info("Loaded " + m)

@bot.event
async def on_ready():
    log.info("Ready as " + str(bot.user))
    bot.uptime = time.time()
    await presence.change_presence(bot)
    if not settings.BETA:
        await presence.post_stats(bot)

@bot.event
async def on_guild_join(guild):
    log.info("Joined guild {0.name} / {0.id}".format(guild))
    await presence.change_presence(bot)
    if not settings.BETA:
        await presence.post_stats(bot)

@bot.event
async def on_guild_remove(guild):
    log.info("Left guild {0.name} / {0.id}".format(guild))
    await presence.change_presence(bot)
    if not settings.BETA:
        await presence.post_stats(bot)

@bot.event
async def on_command(ctx):
    bot.cmds += 1

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, discord.Forbidden):
        pass
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can't be used in private messages.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to run this command.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send("You can run this command in {} seconds.".format(round(error.retry_after, 1)))
    else:
        log.error(str(error))
        e = discord.Embed(color=discord.Color.red(), title="An error occurred")
        e.description = "Please report this error to the developers at https://discord.me/konomi.\n```\n{}\n```".format(error)
        await ctx.send(embed=e)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    elif message.content.lower().startswith("twitch "):
        if message.content.lower() == "twitch help":
            return await message.channel.send(embed=presence.send_help_content())
        else:
            await bot.process_commands(message)

try:
    #bot.loop.create_task(poll_twitch())
    if settings.BETA:
        bot.run(settings.BETA_TOKEN, bot=True, reconnect=True)
    else:
        bot.run(settings.TOKEN, bot=True, reconnect=True)
except KeyboardInterrupt:
    f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
    f.write(json.dumps(bot.notifs))
    f.close()
    loop.run_until_complete(bot.logout())
except:
    log.fatal(traceback.format_exc())
