from discord.ext import commands
import discord, asyncio
import logging, traceback
import json
import os, sys, platform
import time
from utils import presence, settings, lang, http
from utils.exceptions import TooManyRequestsError
from utils.functions import LogFilter
import datadog
import sentry_sdk
import tinydb
import rethinkdb as r
r = r.RethinkDB()

log = logging.getLogger("bot.core")
# suppress 'unknown event' warnings
gateway = logging.getLogger("discord.gateway")
gateway.addFilter(LogFilter())
if not settings.UseBetaBot:
    sentry_sdk.init(settings.SentryKey)
    datadog.initialize(api_key=settings.Datadog.APIKey, app_key=settings.Datadog.AppKey)
logging.basicConfig(
    level=logging.INFO if settings.UseBetaBot else logging.WARN,
    format='%(levelname)s %(name)s @ %(asctime)s >> %(message)s',
    datefmt='%H:%M.%S'
)

modules = [
    "jishaku",
    "cogs.general",
    "cogs.games",
    "cogs.audio",
    "cogs.live",
    "cogs.dev",
    "cogs.filter",
#    "cogs.streamlabs",
    "cogs.twitch",
    "cogs.guild"
]
clustered = False
try:
    shards = list(map(lambda m: int(m), sys.argv[sys.argv.index('shards')+1].split(',')))
    shard_count = int(sys.argv[sys.argv.index('shard_count')+1])
    clustered = True
    logging.warn(f"shards: {str(shards)}")
    logging.warn(f"total shards: {shard_count}")
except ValueError as e:
    logging.warn(f'Shard IDs / shard count was not specified, letting AutoShardedBot take over ({e})')
except TypeError:
    logging.error('Shards IDs and shard count must be \'int\'')

rethink_opts = {
    "host": settings.RethinkDB.Host,
    "port": settings.RethinkDB.Port,
    "db": "TwitchBotCanary" if settings.UseBetaBot else "TwitchBot"
}

bot = None

def init(opts):
    # temporary hack-ish init function
    global bot
    bot = commands.AutoShardedBot(**opts)
    bot.rethink = r.connect(**rethink_opts)
    bot.cmds = 0
    bot.vc = {}
    bot.game_cache = {}
    bot.uptime = 0
    bot.clip_votes = {}
    bot.tw_access_token = {}

    for m in modules:
        try:
            bot.load_extension(m)
        except:
            log.error(f"Failed to load {m}:\n{traceback.format_exc()}")
        else:
            log.debug("Loaded " + m)
    log.info(f"Loaded {len(modules)} modules")

    @bot.event
    async def on_ready():
        print("""
      _____          _ _       _     ____        _
     |_   _|_      _(_) |_ ___| |__ | __ )  ___ | |_
       | | \\ \\ /\\ / / | __/ __| '_ \\|  _ \\ / _ \\| __|
       | |  \\ V  V /| | || (__| | | | |_) | (_) | |_
       |_|   \\_/\\_/ |_|\\__\\___|_| |_|____/ \\___/ \\__|
        """)
        print(f"discord.py version: {discord.__version__}")
        print(f"Python version: {platform.python_version()}")
        print(f"Running on: {platform.system()} v{platform.version()}")
        print(f"Discord user: {bot.user} / {bot.user.id}")
        print(f"Connected guilds: {len(bot.guilds)}")
        print(f"Connected users: {len(list(bot.get_all_members()))}")
        print(f"Shard IDs: {getattr(bot, 'shard_ids', None)}")
        bot.uptime = time.time()
        await presence.change_presence(bot)
        datadog.statsd.increment('bot.ready_events')

    @bot.event
    async def on_command(ctx):
        commands.Cooldown(1, 5, commands.BucketType.user).update_rate_limit()
        bot.cmds += 1
        if not settings.UseBetaBot:
            datadog.statsd.increment('bot.commands_run', tags=[f"command:{ctx.command}"])

    @bot.event
    async def on_command_error(ctx, error):
        msgs = await lang.get_lang(ctx)
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        if isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, discord.Forbidden):
            try:
                await ctx.send(msgs['errors']['forbidden'])
            except:
                pass
        elif isinstance(error, discord.NotFound):
            await ctx.send(msgs['errors']['not_found'])
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send(msgs['permission']['no_pm'])
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(msgs['errors']['check_fail'])
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(msgs['errors']['missing_arg'].format(param=error.param))
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(msgs['errors']['cooldown'].format(time=round(error.retry_after, 1)))
        elif isinstance(error, KeyError) or isinstance(error, IndexError):
            await ctx.send(msgs['games']['no_results'])
        elif isinstance(error, TooManyRequestsError):
            await ctx.send(msgs['errors']['too_many_requests'])
        elif isinstance(error, discord.ConnectionClosed) or isinstance(error, asyncio.CancelledError):
            await ctx.send(msgs['errors']['conn_closed'].format(reason=error.reason))
        elif isinstance(error, commands.BadArgument):
            if "notif add" in ctx.message.content:
                return await ctx.send(msgs['errors']['not_found'])
        else:
            logging.error(f"{type(error).__name__} in command '{ctx.command}': {error}")
            sentry_sdk.capture_exception(error)
            e = discord.Embed(color=discord.Color.red(), title=msgs['games']['generic_error'])
            e.description = f"{msgs['errors']['err_report']}\n```\n{type(error).__name__}: {error}\n```"
            await ctx.send(embed=e)
            if ctx.message.guild:
                await http.SendMetricsWebhook("{0.author} {0.author.id} in {0.guild.name} {0.guild.id}: error in `{0.content}`: `{1}: {2}`".format(ctx.message, type(error).__name__, error))
            else:
                await http.SendMetricsWebhook("{0.author} {0.author.id} in DM: error in `{0.content}`: `{1}: {2}`".format(ctx.message, type(error).__name__, error))

    @bot.command(hidden=True, name="reload")
    async def _reload(ctx, cog):
        if not ctx.author.id == 236251438685093889: return
        try:
            bot.unload_extension(cog)
            bot.load_extension(cog)
        except Exception as e:
            await ctx.send("Failed to reload cog: `{}`".format(e))
        else:
            await ctx.send("Successfully reloaded cog.")

    return bot

def run(bot):
    lang.load_langs(bot)
    try:
        if settings.UseBetaBot:
            bot.run(settings.BetaToken, bot=True, reconnect=True)
        else:
            bot.run(settings.Token, bot=True, reconnect=True)
    except KeyboardInterrupt:
        loop.run_until_complete(bot.logout())
    except:
        log.fatal(traceback.format_exc())

if __name__ == "__main__":
    opts = {
        "command_prefix": ["twbeta ", "twb>"] if settings.UseBetaBot else ["twitch ", "Twitch ", "!twitch ", "tw>"],
        "owner_id": 236251438685093889
    }
    if clustered:
        opts['shard_ids'] = shards
        opts['shard_count'] = shard_count
    bot = init(opts)
    run(bot)
