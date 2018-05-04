from discord.ext import commands
from utils import settings
import discord
import time
import json

class Dev:
    def __init__(self, bot):
        self.bot = bot

    def owner_only(ctx):
        return ctx.message.author.id == "236251438685093889"

    def check_fail(ctx):
        return False

    @commands.command()
    @commands.check(owner_only)
    async def error(self, *args):
        raise RuntimeError()

    @commands.command()
    @commands.check(owner_only)
    async def args(self, *args):
        await self.bot.say(", ".join(args))

    @commands.command()
    @commands.check(check_fail)
    async def fail_check(self):
        await self.bot.say("I don't know how you passed this check, but congrats! :tada:")

    @commands.command()
    @commands.check(owner_only)
    async def ratelimits(self):
        m = ""
        for r in self.bot.ratelimits.keys():
            m += "**{}**: {} ({})\n".format(r, self.bot.ratelimits[r], time.strftime('%m/%d/%Y %H:%M.%S', time.localtime(self.bot.ratelimits[r])))
        await self.bot.say(m)

    @commands.command(pass_context=True)
    @commands.check(owner_only)
    async def send_raw_embed(self, ctx, *, jsonstuff):
        token = settings.TOKEN
        if settings.BETA:
            token = settings.BETA_TOKEN
        r = requests.post("https://discordapp.com/api/channels/{}/messages".format(channel_id), headers={"Authorization": "Bot " + token, "Content-Type": "multipart/form-data"}, files=dict(content=jsonstuff))
        await self.bot.say("```\nPOST {0.url} {0.status_code}\n\n{1}\n```".format(r, r.json()))

def setup(bot):
    bot.add_cog(Dev(bot))
