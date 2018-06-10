from discord.ext import commands
from utils import settings
import discord
import time
import traceback
import json

class Dev:
    def __init__(self, bot):
        self.bot = bot

    def owner_only(ctx):
        return ctx.message.author.id == 236251438685093889

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

    @commands.command(hidden=True, name="eval")
    async def _eval(self, ctx, *, code):
        if not ctx.author.id == 236251438685093889: return
        try:
            e = eval(code)
            await ctx.send("```py\n{}\n```".format(e))
        except Exception as e:
            await ctx.send("```py\n{}: {}\n```".format(type(e).__name__, e))

    @commands.command()
    @commands.check(owner_only)
    async def error(self, ctx, *args):
        raise RuntimeError()

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
            stuff = ""
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
                stuff += "{p} {s} : Guilds: {g} Members: {m} Latency: {l}ms\n".format(p=pre, s=s, g=len(servers[str(s)]), m=members[str(s)], l=dict(self.bot.latencies)[int(s)] * 1000)
            await ctx.send("```prolog\n{}```".format(stuff))
        except:
            await ctx.send(traceback.format_exc())

def setup(bot):
    bot.add_cog(Dev(bot))
