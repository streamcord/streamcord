from discord.ext import commands
import discord, asyncio
import logging, traceback
import json
import os, sys
import time
import aiohttp

from utils import presence
from utils import settings

logging.basicConfig(level=logging.INFO, format='%(levelname)s/%(module)s @ %(asctime)s: %(message)s', datefmt='%I:%M:%S %p')
log = logging.getLogger("bot.core")

modules = ["mod.general", "mod.users", "mod.games", "mod.streams", "mod.audio", "mod.notifs", "mod.stats", "mod.dev", "mod.clips", "mod.live_check", "mod.perspective"]
if settings.BETA:
    prefix = ["twbeta ", "Twbeta "]
else:
    prefix = ["twitch ", "Twitch "]

bot = commands.AutoShardedBot(command_prefix=prefix)
bot.remove_command('help')
bot.notifs = json.loads(open(os.path.join(os.getcwd(), 'data', 'notifs.json')).read())
bot.livecheck = json.loads(open(os.path.join(os.getcwd(), 'data', 'live.json')).read())
bot.perspective = json.loads(open(os.path.join(os.getcwd(), 'data', 'perspective.json')).read())
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
    elif message.content.lower().startswith(prefix[0]):
        if message.content.lower() == prefix[0] + "help":
            return await message.channel.send(embed=presence.send_help_content())
        else:
            await bot.process_commands(message)
    elif message.guild is None:
        return
    elif str(message.guild.id) in bot.perspective.keys() and len(message.clean_content) > 5:
        async with aiohttp.ClientSession() as session:
            payload = {
                "comment": {"text": message.clean_content},
                "languages": ["en"],
                "requestedAttributes": {
                    "SEVERE_TOXICITY": {}
                }
            }
            async with session.post("https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key=" + settings.Google.PERSPECTIVE_API_KEY, data=json.dumps(payload)) as r:
                response = await r.json()
                if r.status != 200:
                    log.error("HTTP {r.status} on {r.url}".format(r=r))
                    log.error(str(response))
                    return
                score = response["attributeScores"]["SEVERE_TOXICITY"]["summaryScore"]["value"]
                log.debug("Evaluated message from {message.author.id} -> \"{message.clean_content}\" (score: {score})".format(message=message, score=score * 100))
                if score * 100 >= bot.perspective[str(message.guild.id)]:
                    log.debug("detected toxic comment")
                    await message.delete()
                    await message.channel.send("{}, your message was deleted because it scored higher than the server's maximum toxicity range. (Score: {}/{})".format(message.author.name, round(score * 100, 1), bot.perspective[str(message.guild.id)]))

@bot.event
async def on_member_update(before, after):
    if before.guild is None:
        return None
    elif before.bot:
        return None
    elif bot.livecheck.get(after.guild.id) is None:
        return None
    before_streaming = isinstance(before.activity, discord.Streaming)
    after_streaming = isinstance(after.activity, discord.Streaming)
    role = discord.utils.find(lambda r: r.id == bot.livecheck[after.guild.id], after.guild.roles)
    if role is None:
        del bot.livecheck[after.guild.id]
    if before_streaming != after_streaming:
        log.debug("Adding streamer role to {before.id} in {before.guild.id}".format(before))
    elif (not before_streaming) and after_streaming:
        await after.add_roles(role, reason="User went live on Twitch")
    elif before_streaming and (not after_streaming):
        await after.remove_roles(role, reason="User no longer live on Twitch")


try:
    if settings.BETA:
        bot.run(settings.BETA_TOKEN, bot=True, reconnect=True)
    else:
        bot.run(settings.TOKEN, bot=True, reconnect=True)
except KeyboardInterrupt:
    f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
    f.write(json.dumps(bot.notifs))
    f.close()
    f2 = open(os.path.join(os.getcwd(), 'data', 'live.json'), 'w')
    f2.write(json.dumps(bot.livecheck))
    f2.close()
    loop.run_until_complete(bot.logout())
except:
    log.fatal(traceback.format_exc())
