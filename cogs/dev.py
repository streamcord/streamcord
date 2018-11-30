from discord.ext import commands
from utils import settings
import discord, asyncio
import time
import traceback
import json, io
import textwrap
from contextlib import redirect_stdout
from collections import Counter, OrderedDict
from operator import itemgetter
from subprocess import PIPE
import sys

class Dev:
    def __init__(self, bot):
        self.bot = bot

    def cleanup_code(self, content):
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])
        return content.strip('` \n')

    def owner_only(ctx):
        return ctx.author.id in [236251438685093889, 388424304678666240]

    def check_fail(ctx):
        return False

    @commands.command(hidden=True, name="reload")
    async def _reload(self, ctx, cog):
        if not ctx.author.id == 236251438685093889: return
        try:
            self.bot.unload_extension(cog)
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send("Failed to reload cog: `{}`".format(e))
        else:
            await ctx.send("Successfully reloaded cog.")

    @commands.command(name="eval")
    async def _eval(self, ctx, *, body: str):
        if not ctx.author.id == 236251438685093889: return

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
            value = stdout.getvalue().replace(settings.TOKEN, "insert token here")
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue().replace(settings.TOKEN, "insert token here")
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
    @commands.check(owner_only)
    async def error(self, ctx, *args):
        raise RuntimeError()

    @commands.command()
    @commands.check(owner_only)
    async def test(self, ctx):
        await self.bot.get_channel(467334911314100234).send("oof")

    @commands.check(owner_only)
    async def test2(self, ctx):
        await self.bot.get_channel(1).send("oof")

    @commands.command()
    @commands.check(owner_only)
    async def args(self, ctx, *args):
        await ctx.send(", ".join(args))

    @commands.command()
    @commands.check(check_fail)
    async def fail_check(self, ctx):
        await ctx.send("I don't know how you passed this check, but congrats! :tada:")

    @commands.command()
    @commands.check(owner_only)
    async def ratelimits(self, ctx):
        m = ""
        for r in self.bot.ratelimits.keys():
            m += "**{}**: {} ({})\n".format(r, self.bot.ratelimits[r], time.strftime('%m/%d/%Y %H:%M.%S', time.localtime(self.bot.ratelimits[r])))
        await ctx.send(m)

    @commands.command()
    async def shardinfo(self, ctx):
        try:
            stuff = "  All : Guilds: {g} Members: {m} Latency: {l}ms\n".format(g=len(self.bot.guilds), m=len(list(self.bot.get_all_members())), l=round(self.bot.latency*1000, 2))
            servers = {}
            members = {}
            for guild in self.bot.guilds:
                shard = str(guild.shard_id)
                if servers.get(str(shard)) is None:
                    servers[shard] = [guild]
                    members[shard] = len(guild.members)
                else:
                    servers[shard].append(guild)
                    members[shard] += len(guild.members)
            for s in range(0, self.bot.shard_count):
                pre = "  "
                if ctx.guild.shard_id == s:
                    pre = "->"
                if len(str(s)) == 2:
                    stuff += "{p} {s} : Guilds: {g} Members: {m} Latency: {l}ms\n".format(p=pre, s=s, g=len(servers[str(s)]), m=members[str(s)], l=round(dict(self.bot.latencies)[int(s)] * 1000, 2))
                else:
                    stuff += " {p} {s} : Guilds: {g} Members: {m} Latency: {l}ms\n".format(p=pre, s=s, g=len(servers[str(s)]), m=members[str(s)], l=round(dict(self.bot.latencies)[int(s)] * 1000, 2))
            await ctx.send("```prolog\n{}```".format(stuff))
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

    @commands.command()
    @commands.check(owner_only)
    async def speedtest(self, ctx):
        m = await ctx.send("Running speedtest... <a:updating:403035325242540032>")
        proc = await asyncio.create_subprocess_shell("speedtest-cli --simple", stdin=None, stderr=PIPE, stdout=PIPE)
        out = (await proc.stdout.read()).decode('utf-8').strip()
        await m.edit(content="```prolog\n{}```".format(out))

    @commands.command()
    @commands.check(owner_only)
    async def restart(self, ctx):
        await ctx.send("Restarting...")
        sys.exit(0)
        return await ctx.send("apparently the restart command doesn't work")


def setup(bot):
    bot.add_cog(Dev(bot))
