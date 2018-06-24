from discord.ext import commands
import discord, asyncio
import logging, traceback
import json
import os, sys
import time
import aiohttp
import websockets, ssl
from quart import Quart, request

from utils import presence
from utils import settings

global app
app = Quart(__name__)

logging.basicConfig(level=logging.INFO, format='%(levelname)s/%(module)s @ %(asctime)s: %(message)s', datefmt='%I:%M:%S %p')
log = logging.getLogger("bot.core")

modules = ["cogs.general", "cogs.users", "cogs.games", "cogs.streams", "cogs.audio", "cogs.notifs", "cogs.stats", "cogs.dev", "cogs.clips", "cogs.live_check", "cogs.moderation"]
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
    livecheck = list(bot.livecheck.keys()) # Copy so we don't get 'dictionary changed size during iteration'
    for guild in livecheck:
        g = bot.get_guild(int(guild))
        if g is None:
            del bot.livecheck[guild]
        else:
            role = discord.utils.find(lambda r: r.id == bot.livecheck[str(g.id)], g.roles)
            for m in filter(lambda m: isinstance(m.activity, discord.Streaming), g.members):
                if not m.bot:
                    log.info("Adding streamer role to {before.id} in {before.guild.id}".format(before=m))
                    await m.add_roles(role, reason="User went live on Twitch")
            for m in filter(lambda m: discord.utils.get(m.roles, id=guild) is not None, g.members):
                if not isinstance(m.activity, discord.Streaming):
                    if not m.bot:
                        log.info("Removing streamer role from {before.id} in {before.guild.id}".format(before=m))
                        await m.remove_roles(role, reason="User no longer live on Twitch")

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
    if isinstance(error, commands.CommandNotFound) or isinstance(error, discord.Forbidden):
        pass
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can't be used in private messages.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to run this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You're missing the '{}' argument.".format(error.param))
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send("You can run this command in {} seconds.".format(round(error.retry_after, 1)))
    elif isinstance(error, commands.CommandInvokeError):
        log.error(str(error.original))
        e = discord.Embed(color=discord.Color.red(), title="An error occurred")
        e.description = "Please report this error to the developers at https://discord.me/konomi.\n```\n{}\n```".format(error.original)
        await ctx.send(embed=e)
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
                log.info("Evaluated message from {message.author.id} -> \"{message.clean_content}\" (score: {score})".format(message=message, score=score * 100))
                if score * 100 >= bot.perspective[str(message.guild.id)]:
                    log.info("detected toxic comment")
                    await message.delete()
                    await message.channel.send("{}, your message was deleted because it scored higher than the server's maximum toxicity range. (Score: {}/{})".format(message.author.name, round(score * 100, 1), bot.perspective[str(message.guild.id)]))

@bot.event
async def on_member_update(before, after):
    if before.guild is None:
        return None
    elif before.bot:
        return None
    elif bot.livecheck.get(str(after.guild.id)) is None:
        return None
    log.debug("member update: " + str(after))
    before_streaming = isinstance(before.activity, discord.Streaming)
    after_streaming = isinstance(after.activity, discord.Streaming)
    log.debug(str(before_streaming) + " -> " + str(after_streaming))
    role = discord.utils.find(lambda r: r.id == bot.livecheck[str(after.guild.id)], after.guild.roles)
    if role is None:
        del bot.livecheck[str(after.guild.id)]
    if before_streaming != after_streaming:
        log.info("Modifying streamer role for {before.id} in {before.guild.id}".format(before=before))
    if (not before_streaming) and after_streaming:
        await after.add_roles(role, reason="User went live on Twitch")
    if before_streaming and (not after_streaming):
        await after.remove_roles(role, reason="User no longer live on Twitch")

game_cache = {}

@app.route('/webhook')
async def webhook():
    jsond = request.json
    slist = jsond['data']
    for stream in slist:
        if bot.notifs.get(str(stream['user_id'])):
            meta = bot.notifs[stream['user_id']]
            if stream['type'] == 'live':
                    for channel_id in meta.keys():
                        obj = meta[channel_id]
                        if not obj['last_stream_id'] == stream['id']:
                            bot.notifs[stream['user_id']][channel_id]['last_stream_id'] = stream['id']
                            e = discord.Embed(color=discord.Color(0x6441A4))
                            e.title = stream['title']
                            game = "null"
                            if game_cache.get(stream['game_id']) is None:
                                r2 = STREAM_REQUEST("https://api.twitch.tv/helix/games?id=" + stream['game_id'])
                                if r2.status_code > 299:
                                    TRIGGER_WEBHOOK("Stream request returned non-2xx status code: {}\n```json\n{}\n```".format(r2.status_code, r2.json()))
                                else:
                                    game = r2.json()['data'][0]['name']
                                    game_cache[stream['game_id']] = game
                            else:
                                game = game_cache[stream['game_id']]
                            e.description = "Playing {} for {} viewers".format(game, stream['viewer_count'])
                            e.set_image(url=stream['thumbnail_url'].format(width=1920, height=1080))
                            try:
                                await bot.get_channel(channel_id).send(obj['message'], embed=e)
                            except discord.Forbidden:
                                pass
                            except:
                                TRIGGER_WEBHOOK("Failed to send message: ```\n{}\n```".format(traceback.format_exc()))

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
