from discord.ext import commands
from utils import settings, lang, paginator, presence
import discord, asyncio, aiohttp
import time
import traceback
import json, io
import textwrap
from contextlib import redirect_stdout
from collections import Counter, OrderedDict
from operator import itemgetter
from subprocess import PIPE
import sys
import datadog, logging
import websockets.exceptions as ws
import rethinkdb as r
r = r.RethinkDB()

class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not settings.UseBetaBot:
            bot.loop.create_task(self.background_dd_report())
        bot.loop.create_task(self.daily_bot_stats())

    def cleanup_code(self, content):
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])
        return content.strip('` \n')

    def owner_only(ctx):
        return ctx.author.id in settings.BotOwners

    @commands.check(owner_only)
    @commands.command(name="eval", hidden=True)
    async def _eval(self, ctx, *, body: str):
        if not ctx.author.id in settings.BotOwners: return
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

        body = self.cleanup_code(body)
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
            value = stdout.getvalue().replace(settings.Token, "insert token here")
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue().replace(settings.Token, "insert token here")
            try:
                await ctx.message.add_reaction('✅')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                await ctx.send(f'```py\n{value}{ret}\n```')

    @commands.command()
    async def shardinfo(self, ctx):
        try:
            servers = {"all": self.bot.guilds}
            members = {"all": len(list(self.bot.get_all_members()))}
            for guild in self.bot.guilds:
                shard = str(guild.shard_id)
                if servers.get(str(shard)) is None:
                    servers[shard] = [guild]
                    members[shard] = len(guild.members)
                else:
                    servers[shard].append(guild)
                    members[shard] += len(guild.members)
            max_shard = max([len(str(x)) for x in range(self.bot.shard_count)])
            max_guild = max([len(str(len(x))) for x in servers.values()])
            max_mbr = max([len(str(x)) for x in members.values()])
            pgr = commands.Paginator(prefix="```prolog")
            pgr.add_line(f"  All : Guilds: {len(servers['all'])} Members: {members['all']} Latency: {round(self.bot.latency*1000, 2)}ms")
            for s in range(0, self.bot.shard_count):
                pre = "  "
                if ctx.guild.shard_id == s:
                    pre = "->"
                pre = " "*(max_shard-len(str(s))) + pre
                pre2 = " "*(max_guild-len(str(len(servers[str(s)]))))
                pre3 = " "*(max_mbr-len(str(members[str(s)])))
                pgr.add_line(f"{pre} {s} : Guilds: {len(servers[str(s)])}{pre2} Members: {members[str(s)]}{pre3} Latency: {round(dict(self.bot.latencies)[int(s)] * 1000, 2)}ms")
            p = paginator.DiscordPaginationExtender(pgr.pages)
            await p.page(ctx)
        except:
            await ctx.send(traceback.format_exc())

    @commands.command()
    async def guildregions(self, ctx):
        unsorted = Counter(map(lambda g: str(g.region), self.bot.guilds))
        data = OrderedDict(sorted(unsorted.items(), key=itemgetter(1), reverse=True))
        stuff = ""
        max_len = len(max(data.keys(), key=len))
        pct_max_len = len(str(max(data.values())))
        for reg in data.keys():
            wsp = max_len - len(reg)
            pct = round(data[reg] / len(self.bot.guilds) * 100, 1)
            pct_wsp = pct_max_len - len(str(data[reg]))
            stuff += "{}{}: {} {} --> {}%\n".format(' '*wsp, reg.title().strip('-'), data[reg], ' '*pct_wsp, pct)
        await ctx.send("```prolog\n{}```".format(stuff))

    @commands.command(hidden=True)
    @commands.check(owner_only)
    async def speedtest(self, ctx):
        m = await ctx.send("Running speedtest... <a:updating:403035325242540032>")
        proc = await asyncio.create_subprocess_shell("speedtest-cli --simple", stdin=None, stderr=PIPE, stdout=PIPE)
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
        except:
            await ctx.send(f"```\n{traceback.format_exc()}\n```")
        else:
            await ctx.send(lang._emoji.cmd_success)

    @commands.command(hidden=True)
    @commands.check(owner_only)
    async def error(self, ctx):
        raise RuntimeError()

    async def background_dd_report(self):
        logging.info('[datadog] waiting for bot to send ON_READY')
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await presence.post_stats(self.bot)
            except Exception as e:
                logging.error(f"[datadog] Error posting metrics: {type(e).__name__}: {e}")
            await asyncio.sleep(60)

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
            e.add_field(name="Guilds", value="{:,}".format(len(self.bot.guilds)))
            e.add_field(name="Members", value="{:,}".format(len(list(self.bot.get_all_members()))))
            channel = self.bot.get_channel(508265844200046621)
            await channel.send(embed=e)


def setup(bot):
    bot.add_cog(Dev(bot))

    @bot.event
    async def on_error(event, *args, **kwargs):
        exc = sys.exc_info()
        if isinstance(exc[1], ws.ConnectionClosed):
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
            return logging.error(f"Error {exc[0].__name__} in {event} event:\n{exc}")
        logging.warn(f"Ignored {exc[0].__name__} error in {event} event")
