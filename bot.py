from discord.ext import commands
import discord, asyncio
import logging, traceback
import json
import os, sys, platform
import time
import aiohttp
import re
from random import randint
from utils import presence, settings
from utils.functions import stream_request, SPLIT_EVERY, TRIGGER_WEBHOOK, replace_all
from utils.exceptions import TooManyRequestsError
from collections import Counter
import datadog
import sentry_sdk
import dateutil.parser

log = logging.getLogger("bot.core")
if settings.BETA:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s/%(module)s @ %(asctime)s: %(message)s', datefmt='%I:%M:%S %p')
else:
    sentry_sdk.init(settings.SENTRY)
    datadog.initialize(api_key=settings.Datadog.APIKey, app_key=settings.Datadog.AppKey)
    logging.basicConfig(level=logging.WARN, format='%(levelname)s @ %(asctime)s: %(message)s', datefmt='%I:%M:%S %p')

modules = ["cogs.general", "cogs.users", "cogs.games", "cogs.streams", "cogs.audio", "cogs.notifs", "cogs.stats", "cogs.dev", "cogs.clips", "cogs.live_check", "cogs.filter", "cogs.streamlabs"]
if settings.BETA:
    prefix = ["twbeta ", "Twbeta ", "!twbeta ", "?twbeta "]
    log.warning("!!! Running in development mode !!!")
else:
    prefix = ["twitch ", "Twitch ", "!twitch ", "?twitch "]

bot = commands.AutoShardedBot(command_prefix=prefix)
bot.notifs = json.loads(open(os.path.join(os.getcwd(), 'data', 'notifs.json')).read())
bot.livecheck = json.loads(open(os.path.join(os.getcwd(), 'data', 'live.json')).read())
bot.perspective = json.loads(open(os.path.join(os.getcwd(), 'data', 'perspective.json')).read())
bot.cmds = 0
bot.ratelimits = {"twitch": 0, "fortnite": 0, "rocketleague": 0, "pubg": 0}
bot.vc = {}
bot.game_cache = {}
bot.uptime = 0
bot.last_stream_notifs = 0
bot.donator_roles = settings.DONATOR_ROLES
bot.clip_votes = {}
bot.tw_access_token = {}

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
    print("""
  _____          _ _       _     ____        _
 |_   _|_      _(_) |_ ___| |__ | __ )  ___ | |_
   | | \\ \\ /\\ / / | __/ __| '_ \\|  _ \\ / _ \\| __|
   | |  \\ V  V /| | || (__| | | | |_) | (_) | |_
   |_|   \\_/\\_/ |_|\\__\\___|_| |_|____/ \\___/ \\__|
    """)
    print("discord.py version: " + discord.__version__)
    print("Python version: " + platform.python_version())
    print("Running on: " + platform.system() + " v" + platform.version())
    print("Discord user: {0} (ID: {0.id})".format(bot.user))
    print("Connected guilds: " + str(len(bot.guilds)))
    print("Connected users: " + str(len(list(bot.get_all_members()))))
    bot.uptime = time.time()
    datadog.statsd.increment('bot.ready_events')
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
                    except discord.NotFound:
                        del bot.livecheck[guild]
            for m in filter(lambda m: discord.utils.get(m.roles, id=guild) is not None, g.members):
                if not isinstance(m.activity, discord.Streaming):
                    if not m.bot:
                        try:
                            log.info("Removing streamer role from {before.id} in {before.guild.id}".format(before=m))
                            await m.remove_roles(role, reason="User no longer live on Twitch")
                        except discord.Forbidden:
                            log.info("[live check] forbidden")
                        except discord.NotFound:
                            del bot.livecheck[guild]

@bot.event
async def on_guild_join(guild):
    log.info("Joined guild {0.name} / {0.id}".format(guild))
    await presence.change_presence(bot)
    if not settings.BETA:
        try:
            await presence.post_stats(bot)
            await bot.get_channel(508265844200046621).send(embed=presence.create_guild_join_embed(bot, guild))
        except:
            log.error(traceback.format_exc())
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            if channel.permissions_for(guild.me).send_messages:
                return await channel.send("Hello! <:twitch:404633403603025921> I'm TwitchBot, a bot that helps integrate Discord servers with Twitch. If you need help, type `twitch help`, and if you want to view my commands, type `twitch commands`.")

@bot.event
async def on_guild_remove(guild):
    log.info("Left guild {0.name} / {0.id}".format(guild))
    await presence.change_presence(bot)
    if not settings.BETA:
        try:
            await presence.post_stats(bot)
            await bot.get_channel(508265844200046621).send(embed=presence.create_guild_leave_embed(bot, guild))
        except:
            log.error(traceback.format_exc())

@bot.event
async def on_command(ctx):
    commands.Cooldown(1, 5, commands.BucketType.user).update_rate_limit()
    bot.cmds += 1
    if not settings.BETA:
        datadog.statsd.increment('bot.commands_run', tags=["command:{}".format(ctx.command)])

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        error = error.original
    if isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, discord.Forbidden):
        try:
            await ctx.send("I don't have the correct permissions to do that.")
        except:
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
    elif isinstance(error, discord.ConnectionClosed):
        await ctx.send("The voice connection was closed for the reason `{}`".format(error.reason))
    elif isinstance(error, commands.BadArgument):
        if "notif add" in ctx.message.content:
            return await ctx.send("That Discord channel was not found. Please make sure you're not putting <> around it and that you're `#mention`ing it.")
    else:
        sentry_sdk.capture_exception(error)
        e = discord.Embed(color=discord.Color.red(), title="An error occurred")
        e.description = "Please report this error to the developers at https://discord.me/konomi.\n```\n{}: {}\n```".format(type(error).__name__, error)
        await ctx.send(embed=e)
        if ctx.message.guild:
            TRIGGER_WEBHOOK("{0.author} {0.author.id} in {0.guild.name} {0.guild.id}: error in `{0.content}`: `{1}: {2}`".format(ctx.message, type(error).__name__, error))
        else:
            TRIGGER_WEBHOOK("{0.author} {0.author.id} in DM: error in `{0.content}`: `{1}: {2}`".format(ctx.message, type(error).__name__, error))

@bot.event
async def on_message(message):
    datadog.statsd.increment('bot.messages_received')
    if message.author.bot:
        return
    elif message.content.lower().startswith(tuple(prefix)):
        if message.guild:
            log.info("{0.author} {0.author.id} in {0.guild.name} {0.guild.id}: {0.clean_content}".format(message))
        else:
            log.info("{0.author} {0.author.id} in DM: {0.clean_content}".format(message))
        if message.content.lower() in tuple(map(lambda t: t + "help", prefix)):
            # === Send help command === #
            if not settings.BETA:
                datadog.statsd.increment('bot.commands_run', tags=["command:help"])
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
    try:
        if (not before_streaming) and after_streaming:
            await after.add_roles(role, reason="User went live on Twitch")
        if before_streaming and (not after_streaming):
            await after.remove_roles(role, reason="User no longer live on Twitch")
    except discord.Forbidden:
        log.info("[live check] forbidden")

# example streamer object:
 # {streamer_id:
 #     {discord.TextChannel.id:
 #         {"last_stream_id": stream_id,
 #         "message": message}
 #     }
 # }

async def poll3():
    log.info('[notifs] Waiting for ON_READY...')
    await bot.wait_until_ready()
    while not bot.is_closed():
        if not hasattr(bot, 'aiohttp'):
            bot.aiohttp = aiohttp.ClientSession()
        try:
            log.info('[notifs] looping notification list...')
            notifs = dict(bot.notifs).copy()
            streamers = SPLIT_EVERY(100, notifs)
            page = 0
            bot.last_stream_notifs = time.time()
            for split in streamers:
                page += 1
                logging.info('[notifs] iter page {}/{}'.format(page, len(streamers)))
                if len(list(split.keys())) < 1:
                    logging.info('[notifs] skipping page')
                    continue
                # get stream data
                s = await stream_request(bot, '/streams?user_id={}'.format('&user_id='.join(list(split.keys()))))
                if len(s['data']) <1:
                    logging.info('[notifs] no live users in this page')
                # get user data
                unames = map(lambda stream: stream['user_id'], s['data'])
                u = await stream_request(bot, '/users?id={}'.format('&id='.join(unames)))
                # get games data
                games = Counter(map(lambda stream: stream['game_id'], s['data'])).keys()
                g = await stream_request(bot, '/games?id={}'.format('&id'.join(games)))
                compiled = []
                for stream in s['data']:
                    # get more info on the user streaming and game being played
                    s_user = list(filter(lambda user: user['id'] == stream['user_id'], u['data']))[0]
                    try:
                        s_game = list(filter(lambda game: game['id'] == stream['game_id'], g['data']))[0]
                    except:
                        s_game = {"name": "Unknown", "id": 0}
                    compiled.append({'stream': stream, 'user': s_user, 'game': s_game})
                for stream in compiled:
                    streamer = bot.notifs.get(stream['user']['id'])
                    if streamer == None:
                        logging.warn('[notif] Couldn\'t find record of user {}'.format(stream['user']['id']))
                        continue
                    channels = streamer.copy()
                    if len(list(channels.keys())) == 0:
                        del bot.notifs[stream['user']['id']]
                        logging.info('[notif] User {} has no channels to notify'.format(stream['user']['id']))
                        continue
                    # build the embed
                    e = discord.Embed(color=discord.Color(0x6441A4))
                    e.title = "**{}**".format(stream['stream']['title'])
                    e.description = "\nPlaying {} for {} viewers\n[Watch Stream](https://twitch.tv/{})".format(stream['game']['name'], stream['stream']['viewer_count'], stream['user']['login'])
                    e.timestamp = dateutil.parser.parse(stream['stream']['started_at'])
                    e.url = "https://twitch.tv/" + stream['user']['login']
                    e.set_footer(text="twitchbot.io")
                    author_info = {
                        "name": "{} is now live on Twitch!".format(stream['user']['display_name']),
                        "url": e.url,
                        "icon_url": stream['user']['profile_image_url']
                    }
                    e.set_author(**author_info)
                    e.set_image(url=stream['stream']['thumbnail_url'].format(width=1920, height=1080))
                    for c in channels.keys():
                        try:
                            if bot.notifs[stream['user']['id']][c]['last_stream_id'] == stream['stream']['id']:
                                # already notified for the current stream
                                continue
                        except KeyError:
                            logging.info('[notif] notification for {} in {} must\'ve gotten deleted'.format(stream['user']['id'], c))
                            continue
                        channel = bot.get_channel(int(c))
                        if channel is None:
                            del bot.notifs[stream['user']['id']][c]
                            logging.info('[notif] channel {} does not exist'.format(c))
                            continue
                        try:
                            fmt_vars = {
                                "$title$": stream['stream']['title'],
                                "$viewers$": stream['stream']['viewer_count'],
                                "$game$": stream['game']['name'],
                                "$url$": "https://twitch.tv/{}".format(stream['user']['login']),
                                "$name$": stream['user']['display_name'],
                                "$everyone$": "@everyone",
                                "$here$": "@here"
                            }
                            message_to_send = replace_all(bot.notifs[stream['user']['id']][c]['message'], fmt_vars)
                            await channel.send(message_to_send, embed=e)
                            logging.info('[notif] sent notification for {} in {}'.format(stream['user']['id'], c))
                            bot.notifs[stream['user']['id']][c]['last_stream_id'] = stream['stream']['id']
                            await asyncio.sleep(0.5)
                        except discord.Forbidden as e:
                            del bot.notifs[stream['user']['id']][c]
                            logging.info('[notif] forbidden for channel {}'.format(c))
                            continue
            logging.info("[notif] Looped {} notifs in {} seconds".format(len(bot.notifs), time.time() - bot.last_stream_notifs))
            if not settings.BETA:
                datadog.statsd.histogram('bot.notif_runtime', time.time() - bot.last_stream_notifs)
                TRIGGER_WEBHOOK("Processed {} notifs in {} seconds".format(len(bot.notifs), time.time() - bot.last_stream_notifs))
            await asyncio.sleep(60)
        except Exception as e:
            logging.error(traceback.format_exc())
            datadog.api.Event.create(title="Notification error", text=traceback.format_exc(), alert_type="error")

async def background_dd_report():
    log.info('[datadog] waiting for bot to send ON_READY')
    await bot.wait_until_ready()
    while not bot.is_closed():
        log.info('[datadog] Sending metrics to datadog')
        datadog.statsd.open_buffer()
        datadog.statsd.gauge('bot.voice.active_sessions', len(bot.voice_clients))
        datadog.statsd.gauge('bot.guilds', len(bot.guilds))
        datadog.statsd.gauge('bot.users', len(list(bot.get_all_members())))
        datadog.statsd.gauge('bot.games_cached', len(bot.game_cache))
        datadog.statsd.gauge('bot.notifications', len(bot.notifs))
        datadog.statsd.gauge('bot.live_checks', len(bot.livecheck))
        datadog.statsd.gauge('bot.ws_latency', abs(round(bot.latency*1000)))
        datadog.statsd.close_buffer()
        await asyncio.sleep(60)


bot.loop.create_task(poll3())
if not settings.BETA:
    bot.loop.create_task(background_dd_report())
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
