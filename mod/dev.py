from discord.ext import commands
from utils import settings
import discord
import time
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
        if not ctx.message.author.id == 236251438685093889: return
        try:
            bot.unload_extension(cog)
            bot.load_extension(cog)
        except Exception as e:
            await ctx.send("Failed to reload cog: `{}`".format(e))
        else:
            await ctx.send("Successfully reloaded cog.")

    @commands.command(hidden=True, name="eval")
    async def _eval(self, ctx, *, code):
        if not ctx.message.author.id == 236251438685093889: return
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

    @commands.command(pass_context=True)
    @commands.check(owner_only)
    async def send_raw_embed(self, ctx, *, jsonstuff):
        token = settings.TOKEN
        if settings.BETA:
            token = settings.BETA_TOKEN
        r = requests.post("https://discordapp.com/api/channels/{}/messages".format(channel_id), headers={"Authorization": "Bot " + token, "Content-Type": "multipart/form-data"}, files=dict(content=jsonstuff))
        await ctx.send("```\nPOST {0.url} {0.status_code}\n\n{1}\n```".format(r, r.json()))

def setup(bot):
    bot.add_cog(Dev(bot))
