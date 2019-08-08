# TwitchBot, the best Twitch.tv bot for Discord
# Copyright (C) Akira, 2017-2019
# Proprietary code | Do not redistribute

from discord.ext import commands
from textwrap import dedent
import discord
import asyncio
import logging
import traceback
import datadog
import rethinkdb as r
import platform
import time

from utils import presence, lang, settings, functions, http
from utils.exceptions import TooManyRequestsError
from utils.functions import LogFilter

logging.basicConfig(
    level=logging.INFO,
    handlers=[functions.initColoredLogging()]
)
log = logging.getLogger("bot.core")
gw_log = logging.getLogger("discord.gateway")
gw_log.addFilter(LogFilter())
if not settings.UseBetaBot:
    datadog.initialize(
        api_key=settings.Datadog.APIKey,
        app_key=settings.Datadog.AppKey
    )
r = r.RethinkDB()


class TwitchBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rethink_opts = {
            "host": settings.RethinkDB.Host,
            "port": settings.RethinkDB.Port,
            "db": "TwitchBotCanary" if settings.UseBetaBot else "TwitchBot"
        }
        self.rethink = r.connect(**rethink_opts)
        self.active_vc = {}
        self.uptime = 0
        self.shard_ids = kwargs.get('shard_ids', [0])
        self.cluster_index = round(min(self.shard_ids) / 5)
        self.add_command(self.__reload__)
        modules = [
            "jishaku",
            "cogs.general",
            "cogs.games",
            "cogs.audio",
            "cogs.live",
            "cogs.dev",
            "cogs.twitch"
        ]
        if settings.UseBetaBot:
            modules = [*modules]
        for m in modules:
            try:
                self.load_extension(m)
            except Exception:
                log.error(f"Failed to load {m}:\n{traceback.format_exc()}")
            else:
                log.debug(f"Loaded module {m}")
        log.info(f"Loaded {len(modules)} modules")

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
        await presence.change_presence(self)
        datadog.statsd.increment('bot.ready_events')

    async def on_command(self, ctx):
        commands.Cooldown(1, 5, commands.BucketType.user).update_rate_limit()
        if not settings.UseBetaBot:
            datadog.statsd.increment(
                'bot.commands_run',
                tags=[f"command:{ctx.command}"]
            )

    async def on_command_error(self, ctx, error):
        msgs = await lang.get_lang(ctx)
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, discord.Forbidden):
            try:
                return await ctx.send(msgs['errors']['forbidden'])
            except Exception:
                pass
        handled = {
            KeyError: msgs['games']['no_results'],
            IndexError: msgs['games']['no_results'],
            TooManyRequestsError: msgs['errors']['too_many_requests'],
            asyncio.CancelledError:
                msgs['errors']['conn_closed']
                .format(reason=getattr(error, 'reason', 'disconnected')),
            discord.ConnectionClosed:
                msgs['errors']['conn_closed']
                .format(reason=getattr(error, 'reason', 'disconnected')),
            discord.NotFound: msgs['errors']['not_found'],
            commands.NoPrivateMessage: msgs['permissions']['no_pm'],
            commands.CheckFailure: msgs['errors']['check_fail'],
            commands.MissingRequiredArgument:
                msgs['errors']['missing_arg']
                .format(param=getattr(error, 'param', None)),
            commands.CommandOnCooldown:
                msgs['errors']['cooldown']
                .format(time=round(getattr(error, 'retry_after', 1), 1)),
            commands.BadArgument:
                msgs['errors']['not_found'] if ctx.command == "notif_add"
                else "Invalid argument."
        }
        try_handled_msg = handled.get(type(error))
        if try_handled_msg is not None:
            return await ctx.send(try_handled_msg)
        # -- Unhandled exceptions -- #
        logging.fatal(f"{type(error).__name__}")
        e = discord.Embed(
            title=msgs['games']['generic_error'],
            description=msgs['errors']['err_report'] +
            f"\n```\n{type(error).__name__}: {error}\n```",
            color=discord.Color.red()
        )
        await ctx.send(embed=e)

    @commands.command(hidden=True, name="reload")
    async def __reload__(self, ctx, cog):
        if ctx.author.id not in settings.BotOwners:
            return
        try:
            ctx.bot.unload_extension(cog)
            ctx.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f"Failed to reload cog: `{type(e).__name__}: {e}`")
        else:
            await ctx.message.add_reaction(
                lang._emoji.cmd_success.strip(" ").strip(">")
            )


def run(bot):
    lang.load_langs(bot)
    try:
        if settings.UseBetaBot:
            bot.run(settings.BetaToken, bot=True, reconnect=True)
        else:
            bot.run(settings.Token, bot=True, reconnect=True)
    except KeyboardInterrupt:
        bot.loop.run_until_complete(bot.logout())
    except Exception:
        log.fatal(traceback.format_exc())


if __name__ == "__main__":
    run(TwitchBot(
        command_prefix=["twbeta ", "twb>"] if settings.UseBetaBot
        else ["twitch ", "Twitch ", "!twitch ", "tw>"],
        owner_id=236251438685093889
    ))
