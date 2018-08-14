from discord.ext import commands
import discord, asyncio
import logging, traceback
import json
import os, sys
import time
import aiohttp
from random import randint
from utils import presence
from utils import settings
from utils.functions import STREAM_REQUEST, SPLIT_EVERY, TRIGGER_WEBHOOK
from utils.exceptions import TooManyRequestsError
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(levelname)s/%(module)s @ %(asctime)s: %(message)s', datefmt='%I:%M:%S %p')
log = logging.getLogger("bot.core")

modules = ["cogs.general", "cogs.bits", "cogs.users", "cogs.games", "cogs.streams", "cogs.audio", "cogs.notifs", "cogs.stats", "cogs.dev", "cogs.clips", "cogs.live_check", "cogs.moderation"]
if settings.BETA:
    prefix = ["twbeta ", "Twbeta "]
    log.warning("!!! Running in development mode !!!")
else:
    prefix = ["twitch ", "Twitch ", "!twitch ", "?twitch "]

bot = commands.AutoShardedBot(command_prefix=prefix)
bot.notifs = json.loads(open(os.path.join(os.getcwd(), 'data', 'notifs.json')).read())
bot.livecheck = json.loads(open(os.path.join(os.getcwd(), 'data', 'live.json')).read())
bot.perspective = json.loads(open(os.path.join(os.getcwd(), 'data', 'perspective.json')).read())
#bot.bits = json.loads(open(os.path.join(os.getcwd(), 'data', 'bits.json')).read())
bot.cmds = 0
bot.ratelimits = {"twitch": 0, "fortnite": 0, "rocketleague": 0, "pubg": 0}
bot.vc = {}
bot.game_cache = {}
bot.uptime = 0
bot.last_stream_notifs = 0

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
                    try:
                        log.info("Adding streamer role to {before.id} in {before.guild.id}".format(before=m))
                        await m.add_roles(role, reason="User went live on Twitch")
                    except discord.Forbidden:
                        log.info("[live check] forbidden")
            for m in filter(lambda m: discord.utils.get(m.roles, id=guild) is not None, g.members):
                if not isinstance(m.activity, discord.Streaming):
                    if not m.bot:
                        try:
                            log.info("Removing streamer role from {before.id} in {before.guild.id}".format(before=m))
                            await m.remove_roles(role, reason="User no longer live on Twitch")
                        except discord.Forbidden:
                            log.info("[live check] forbidden")

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
    elif isinstance(error, discord.NotFound):
        await ctx.send("That Discord channel was not found. Please make sure you're not putting <> around it and that you're `#mention`ing it.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can't be used in private messages.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to run this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You're missing the '{}' argument.".format(error.param))
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send("You can run this command in {} seconds.".format(round(error.retry_after, 1)))
    elif isinstance(error, KeyError) or isinstance(error, IndexError):
        await ctx.send("No results found.")
    elif isinstance(error, TooManyRequestsError):
        await ctx.send("Too many requests are being made right now. Please try again later.")
    elif isinstance(error, commands.BadArgument):
        if "notif add" in ctx.message.content:
            return await ctx.send("That Discord channel was not found. Please make sure you're not putting <> around it and that you're `#mention`ing it.")
    elif isinstance(error, commands.CommandInvokeError):
        log.error(str(error.original))
        e = discord.Embed(color=discord.Color.red(), title="An error occurred")
        e.description = "Please report this error to the developers at https://discord.me/konomi.\n```\n{}: {}\n```".format(type(error.original).__name__, error.original)
        await ctx.send(embed=e)
        if ctx.message.guild:
            TRIGGER_WEBHOOK("{0.author} {0.author.id} in {0.guild.name} {0.guild.id}: error in `{0.content}`: `{1}: {2}`".format(ctx.message, type(error.original).__name__, error.original))
        else:
            TRIGGER_WEBHOOK("{0.author} {0.author.id} in DM: error in `{0.content}`: `{1}: {2}`".format(ctx.message, type(error.original).__name__, error.original))
    else:
        log.error(str(error))
        e = discord.Embed(color=discord.Color.red(), title="An error occurred")
        e.description = "Please report this error to the developers at https://discord.me/konomi.\n```\n{}: {}\n```".format(type(error).__name__, error)
        await ctx.send(embed=e)
        if ctx.message.guild:
            TRIGGER_WEBHOOK("{0.author} {0.author.id} in {0.guild.name} {0.guild.id}: error in `{0.content}`: `{1}: {2}`".format(ctx.message, type(error).__name__, error))
        else:
            TRIGGER_WEBHOOK("{0.author} {0.author.id} in DM: error in `{0.content}`: `{1}: {2}`".format(ctx.message, type(error).__name__, error))

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    elif message.content.lower().startswith(prefix[0]):
        if message.guild:
            log.info("{0.author} {0.author.id} in {0.guild.name} {0.guild.id}: {0.clean_content}".format(message))
        else:
            log.info("{0.author} {0.author.id} in DM: {0.clean_content}".format(message))
        if message.content.lower() in list(map(lambda t: t + "help", prefix)):
            # === Send help command === #
            return await message.channel.send(embed=presence.send_help_content(message, bot))
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
    # bits
#    if bot.bits.get(str(message.author.id)) is None:
#        bot.bits[str(message.author.id)] = {"bits": 0, "multiplier_nonce": 0, "multiplier": 1.9, "nonce": 0, "votes": 0}
#    if bot.bits[str(message.author.id)]['nonce'] + 60 > time.time():
#        return
#    value = randint(1, 3)
#    if bot.bits[str(message.author.id)]['multiplier_nonce'] + 86400 > time.time():
#        value = value * bot.bits[str(message.author.id)]['multiplier']
#    bot.bits[str(message.author.id)]['bits'] += value
#    bot.bits[str(message.author.id)]['nonce'] = time.time()

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

# example streamer object:
 # {streamer_id:
 #     {discord.TextChannel.id:
 #         {"last_stream_id": stream_id,
 #         "message": message}
 #     }
 # }

async def poll2():
    logr = logging.getLogger("bot.notifs")
    await bot.wait_until_ready()
    while not bot.is_closed():
        logr.info("iter notifs")
        notifs = dict(bot.notifs).copy()
        streamers = SPLIT_EVERY(100, notifs)
        page = 0
        bot.last_stream_notifs = time.time()
        for split in streamers:
            logr.info("Iter page #" + str(page))
            page += 1
            if len(list(split.keys())) < 1:
                continue
            stream_data = await STREAM_REQUEST(bot, "/streams?user_id=" + "&user_id=".join(list(split.keys())))
            if stream_data.status_code > 399:
                TRIGGER_WEBHOOK("Stream request returned non-2xx status code: {}\n```json\n{}\n```".format(stream_data.status_code, stream_data.json()))
                await asyncio.sleep(3)
                continue
            if len(stream_data.json()['data']) < 1:
                logr.info("No live users in this split...")
                await asyncio.sleep(3)
                continue
            await asyncio.sleep(3)
            user_data = await STREAM_REQUEST(bot, "/users?id=" + "&id=".join(map(lambda s: s['user_id'], stream_data.json()['data'])))
            if user_data.status_code > 399:
                TRIGGER_WEBHOOK("Stream request returned non-2xx status code: {}\n```json\n{}\n```".format(stream_data.status_code, stream_data.json()))
                await asyncio.sleep(3)
                continue
            games = Counter(map(lambda s: s['game_id'], stream_data.json()['data'])).keys()
            await asyncio.sleep(1)
            game_data = await STREAM_REQUEST(bot, "/games?id=" + "&id=".join(games))
            if game_data.status_code > 399:
                TRIGGER_WEBHOOK("Stream request returned non-2xx status code: {}\n```json\n{}\n```".format(stream_data.status_code, stream_data.json()))
                await asyncio.sleep(3)
                continue
            compiled = []
            for stream in stream_data.json()['data']:
                user = list(filter(lambda u: u['id'] == stream['user_id'], user_data.json()['data']))[0]
                try:
                    game = list(filter(lambda g: g['id'] == stream['game_id'], game_data.json()['data']))[0]
                except IndexError:
                    game = {"name": "Unknown", "id": 0}
                compiled.append({"stream": stream, "user": user, "game": game})
            for s in compiled:
                channels = dict(bot.notifs[s['user']['id']]).copy()
                if len(list(channels.keys())) == 0:
                    del bot.notifs[s['user']['id']]
                    logr.info('no channels to notify... deleting')
                    continue
                e = discord.Embed(color=discord.Color(0x6441A4))
                e.title = s['stream']['title']
                e.description = "Playing {} for {} viewers\n[Watch on Twitch](https://twitch.tv/{})".format(s['game']['name'], s['stream']['viewer_count'], s['user']['login'])
                e.set_author(name=s['user']['login'], url="https://twitch.tv/{}".format(s['user']['login']), icon_url=s['user']['profile_image_url'])
                e.set_image(url=s['stream']['thumbnail_url'].format(width=1920, height=1080))
                for c in channels.keys():
                    if bot.notifs[s['user']['id']][c]['last_stream_id'] == s['stream']['id']:
                        continue
                    channel = bot.get_channel(int(c))
                    if channel is None:
                        del bot.notifs[s['user']['id']][c]
                        logr.info("channel does not exist... deleting")
                        continue
                    try:
                        await channel.send(bot.notifs[s['user']['id']][c]['message'], embed=e)
                        logr.info('notified in ' + str(c))
                        bot.notifs[s['user']['id']][c]['last_stream_id'] = s['stream']['id']
                        await asyncio.sleep(1)
                    except discord.Forbidden:
                        del bot.notifs[s['user']['id']][c]
                        logr.info("forbidden... deleting")
                        continue
            await asyncio.sleep(3)
        logr.info("Iterated thru {} notifs in {} seconds".format(len(bot.notifs), time.time() - bot.last_stream_notifs))
        await asyncio.sleep(60)

if not settings.BETA:
    bot.loop.create_task(poll2())
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
