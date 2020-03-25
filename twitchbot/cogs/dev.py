import asyncio
import io
import logging
import sys
import textwrap
import time
import traceback
from collections import Counter, OrderedDict
from contextlib import redirect_stdout
from operator import itemgetter
from os import getenv
from subprocess import PIPE
from websockets.exceptions import ConnectionClosed

import discord
from discord.ext import commands

import aiohttp
from rethinkdb import RethinkDB
from ..utils import lang, presence, functions
r = RethinkDB()


def owner_only(ctx):
    return functions.is_owner(ctx.author.id)


class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not functions.is_canary_bot():
            bot.loop.create_task(self.background_dd_report())
        bot.loop.create_task(self.daily_bot_stats())

    @staticmethod
    def cleanup_code(content):
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])
        return content.strip('` \n')

    @commands.command(name="eval", hidden=True)
    @commands.check(owner_only)
    async def _eval(self, ctx, *, body: str):
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            'self': self,
        }

        env.update(globals())

        body = Dev.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue() \
                .replace(getenv('BOT_TOKEN'), "[redacted]")
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue() \
                .replace(getenv('BOT_TOKEN'), "[redacted]")
            try:
                await ctx.message.add_reaction('✅')
            except Exception:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                await ctx.send(f'```py\n{value}{ret}\n```')

    @commands.command()
    async def guildregions(self, ctx):
        unsorted = Counter(map(lambda g: str(g.region), self.bot.guilds))
        data = OrderedDict(
            sorted(unsorted.items(), key=itemgetter(1), reverse=True)
        )
        stuff = ""
        max_len = len(max(data.keys(), key=len))
        pct_max_len = len(str(max(data.values())))
        for reg in data.keys():
            wsp = max_len - len(reg)
            pct = round(data[reg] / len(self.bot.guilds) * 100, 1)
            pct_wsp = pct_max_len - len(str(data[reg]))
            stuff += f"{' '*wsp}{reg.title().strip('-')}: {data[reg]} {' '*pct_wsp} --> {pct}%\n"
        await ctx.send("```prolog\n{}```".format(stuff))

    @commands.command(hidden=True)
    @commands.check(owner_only)
    async def speedtest(self, ctx):
        m = await ctx.send("Running speedtest...")
        proc = await asyncio.create_subprocess_shell(
            "speedtest-cli --simple",
            stdin=None,
            stderr=PIPE,
            stdout=PIPE
        )
        out = (await proc.stdout.read()).decode('utf-8').strip()
        await m.edit(content=f"```prolog\n{out}```")

    @commands.command(hidden=True)
    @commands.check(owner_only)
    async def restart(self, ctx):
        await ctx.send("Restarting...")
        sys.exit(0)
        return await ctx.send("apparently the restart command doesn't work")

    @commands.command(hidden=True)
    @commands.check(owner_only)
    async def reload_langs(self, ctx):
        try:
            lang.reload_langs(self.bot)
        except Exception:
            await ctx.send(f"```\n{traceback.format_exc()}\n```")
        else:
            await ctx.send(lang.emoji.cmd_success)

    @commands.command(hidden=True)
    @commands.check(owner_only)
    async def error(self, ctx):
        raise RuntimeError()

    async def background_dd_report(self):
        logging.info('[statsd] waiting for ready event')
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await presence.post_stats(self.bot)
            except Exception as e:
                logging.error("Error posting statsd: %s: %s", type(e).__name__, e)
            await asyncio.sleep(90)

    async def daily_bot_stats(self):
        await self.bot.wait_until_ready()
        last_rep = None
        while not self.bot.is_closed():
            t = time.localtime()
            while not (t.tm_hour == 20 and t.tm_min == 0):
                await asyncio.sleep(10)
                t = time.localtime()
            if last_rep == t.tm_mday:
                await asyncio.sleep(60)
                continue
            last_rep = t.tm_mday
            e = discord.Embed(color=0x36393f, title="Daily stats report")
            e.add_field(
                name="Guilds",
                value="{:,}".format(len(self.bot.guilds))
            )
            e.add_field(
                name="Members",
                value="{:,}".format(len(self.bot.users))
            )
            channel = self.bot.get_channel(508265844200046621)
            await channel.send(embed=e)


def setup(bot):
    bot.add_cog(Dev(bot))

    @bot.event
    async def on_error(event, *args, **kwargs):
        exc = sys.exc_info()
        if isinstance(exc[1], ConnectionClosed):
            pass
        elif isinstance(exc[1], discord.ConnectionClosed):
            pass
        elif isinstance(exc[1], asyncio.CancelledError):
            pass
        elif isinstance(exc[1], asyncio.IncompleteReadError):
            pass
        elif isinstance(exc[1], aiohttp.client_exceptions.ClientOSError):
            pass
        elif isinstance(exc[1], aiohttp.client_exceptions.ServerDisconnectedError):
            pass
        elif isinstance(exc[1], aiohttp.client_exceptions.ClientConnectorError):
            pass
        elif isinstance(exc[1], aiohttp.client_exceptions.ContentTypeError):
            pass
        elif isinstance(exc[1], discord.HTTPException):
            pass
        else:
            logging.error("Error %s in %s: %s", exc[0].__name__, event, exc)
            return
        logging.warning("Ignored %s error in %s event", exc[0].__name__, event)
