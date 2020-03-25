# Streamcord / TwitchBot, the best Twitch.tv bot for Discord
# Copyright (C) Akira, 2017-2020
# Public build - 03/25/2020

import asyncio
import logging
import platform
import time
from os import getenv
from sys import argv

import datadog
import discord
from discord.ext import commands
from rethinkdb import RethinkDB

from .utils import lang, functions, chttp, ws
from .utils.lang import async_lang
from .utils.functions import LogFilter, dogstatsd

if getenv('VERSION') is None:
    raise RuntimeError('Could not load dotenv')

if not (functions.is_canary_bot() or getenv('ENABLE_PRO_FEATURES') == '1'):
    datadog.initialize(
        api_key=getenv('DD_API_KEY'),
        app_key=getenv('DD_APP_KEY'),
        statsd_host=getenv('DD_AGENT_ADDR'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[functions.LogFormatter.init_logging()])
logging.captureWarnings(True)
log = logging.getLogger('bot.core')
gw_log = logging.getLogger('discord.gateway')
gw_log.addFilter(LogFilter())

r = RethinkDB()
r.set_loop_type('asyncio')


class TwitchBot(commands.AutoShardedBot):
    def __init__(self, *args, i18n_dir=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.active_vc = {}
        self.cluster_index = round(min(self.shard_ids) / 5)
        self.i18n_dir = i18n_dir
        self.shard_ids = kwargs.get('shard_ids', [0])
        self.uptime = 0

        asyncio.get_event_loop().run_until_complete(async_lang.load_languages(self))
        asyncio.get_event_loop().run_until_complete(self._db_connect())

        self.chttp = chttp.BaseCHTTP(self)
        self.chttp_stream = chttp.TwitchCHTTP(self, is_backend=True)
        self.chttp_twitch = chttp.TwitchCHTTP(self, is_backend=False)

        self.add_command(self.__reload__)
        modules = [
            "twitchbot.cogs.general",
            "twitchbot.cogs.games",
            "twitchbot.cogs.audio",
            "twitchbot.cogs.live",
            "twitchbot.cogs.dev",
            "twitchbot.cogs.twitch",
            "twitchbot.cogs.status_channels"
        ]
        # if functions.is_canary_bot():
        #     modules = [*modules]
        if getenv('ENABLE_PRO_FEATURES') == '1':
            modules.append('twitchbot.cogs.moderation')
        for m in modules:
            # don't catch exceptions; it's probably never good to ignore a
            # failed cog in both dev and production environments
            self.load_extension(m)
            log.debug('Loaded module %s', m)
        log.info('Loaded %i modules', len(modules))

        self.ws = ws.ThreadedWebServer(self)
        if 'web-server' not in getenv('SC_DISABLED_FEATURES'):
            self.ws_thread = self.ws.keep_alive()

    async def _db_connect(self):
        ctime = time.time()
        self.rethink = await r.connect(
            host=getenv('RETHINK_HOST'),
            port=int(getenv('RETHINK_PORT')),
            db=getenv('RETHINK_DB'),
            user=getenv('RETHINK_USER'),
            password=getenv('RETHINK_PASS'))
        log.info(
            'Connected to RethinkDB on %s:%s in %ims',
            getenv('RETHINK_HOST'),
            getenv('RETHINK_PORT'),
            round((time.time() - ctime) * 1000))

    async def on_ready(self):
        print(f"""
      _____          _ _       _     ____        _
     |_   _|_      _(_) |_ ___| |__ | __ )  ___ | |_
       | | \\ \\ /\\ / / | __/ __| '_ \\|  _ \\ / _ \\| __|
       | |  \\ V  V /| | || (__| | | | |_) | (_) | |_
       |_|   \\_/\\_/ |_|\\__\\___|_| |_|____/ \\___/ \\__|
        """)
        print(f"discord.py version: {discord.__version__}")
        print(f"Python version: {platform.python_version()}")
        print(f"Running on: {platform.system()} v{platform.version()}")
        print(f"Discord user: {self.user} / {self.user.id}")
        print(f"Connected guilds: {len(self.guilds)}")
        print(f"Connected users: {len(list(self.get_all_members()))}")
        print(f"Shard IDs: {getattr(self, 'shard_ids', None)}")
        print(f"Cluster index: {self.cluster_index}")
        self.uptime = time.time()
        await dogstatsd.increment('bot.ready_events')

    async def on_command(self, ctx):
        commands.Cooldown(1, 5, commands.BucketType.user).update_rate_limit()
        await dogstatsd.increment('bot.commands_run', tags=[f'command:{ctx.command}'])

    async def on_command_error(self, ctx, error):
        msgs = await lang.get_lang(ctx)
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, discord.Forbidden):
            try:
                return await ctx.send(msgs['errors']['forbidden'])
            except discord.Forbidden:
                pass
        if isinstance(error, KeyError):
            error_message = msgs['games']['no_results']
        elif isinstance(error, IndexError):
            error_message = msgs['games']['no_results']
        elif isinstance(error, chttp.exceptions.RatelimitExceeded):
            error_message = msgs['errors']['too_many_requests']
        elif isinstance(error, asyncio.CancelledError):
            error_message = msgs['errors']['conn_closed'].format(
                reason=getattr(error, 'reason', 'disconnected'))
        elif isinstance(error, discord.ConnectionClosed):
            error_message = msgs['errors']['conn_closed'].format(
                reason=getattr(error, 'reason', 'disconnected'))
        elif isinstance(error, discord.NotFound):
            error_message = msgs['errors']['not_found']
        elif isinstance(error, commands.NoPrivateMessage):
            error_message = msgs['permissions']['no_pm']
        elif isinstance(error, commands.CheckFailure):
            error_message = msgs['errors']['check_fail']
        elif isinstance(error, commands.MissingRequiredArgument):
            error_message = msgs['errors']['missing_arg'].format(
                param=getattr(error, 'param', None))
        elif isinstance(error, commands.CommandOnCooldown):
            error_message = msgs['errors']['cooldown'].format(
                time=round(getattr(error, 'retry_after', 1), 1))
        elif isinstance(error, commands.BadArgument):
            error_message = msgs['errors']['not_found'] \
                if ctx.command == "notif_add" \
                else "Invalid argument."
        else:
            # Process unhandled exceptions with an error report
            err = f"{type(error).__name__}: {error}"
            logging.fatal(err)
            e = discord.Embed(
                color=discord.Color.red(),
                title=msgs['games']['generic_error'],
                description=f"{msgs['errors']['err_report']}\n```\n{err}\n```")
            return await ctx.send(embed=e)
        await ctx.send(error_message)

    # pylint: disable=no-self-argument
    @commands.command(hidden=True, name="reload")
    async def __reload__(ctx, cog):
        # pylint: disable=no-member
        if not functions.is_owner(ctx.author.id):
            return
        try:
            ctx.bot.unload_extension(cog)
            ctx.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f"Failed to reload cog: `{type(e).__name__}: {e}`")
        else:
            await ctx.message.add_reaction(
                lang.emoji.cmd_success.strip(" ").strip(">"))

    @staticmethod
    def initialize(i18n_dir=None, shard_count=1, shard_ids=None):
        if functions.is_canary_bot():
            if getenv('ENABLE_PRO_FEATURES') == '1':
                activity = discord.Game(name="with new Pro features")
            else:
                activity = discord.Game(name="with new features")
            prefixes = ["twbeta ", "tb "]
            status = discord.Status.idle
        else:
            if getenv('ENABLE_PRO_FEATURES') == '1':
                activity = discord.Streaming(
                    name="?twitch help · streamcord.io/twitch/pro",
                    url="https://twitch.tv/streamcord_io")
                prefixes = ["?twitch ", "?Twitch "]
            else:
                activity = discord.Streaming(
                    name="!twitch help · streamcord.io/twitch",
                    url="https://twitch.tv/streamcord_io")
                prefixes = ["twitch ", "Twitch ", "!twitch ", "t "]
            status = discord.Status.online

        bot = TwitchBot(
            activity=activity,
            command_prefix=prefixes,
            i18n_dir=i18n_dir,
            owner_id=236251438685093889,
            shard_count=shard_count,
            shard_ids=list(shard_ids),
            status=status)
        return bot
