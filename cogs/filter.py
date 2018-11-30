import discord, asyncio
import traceback
from discord.ext import commands
from utils.functions import TWAPI_REQUEST
import json
import os

class Filter:
    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True)
    async def filter(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Type `twitch help filter` to view command usage.")

    @filter.command(pass_context=True)
    async def set(self, ctx, sensitivity: int):
        sender = self.bot.get_guild(294215057129340938).get_member(ctx.author.id)
        if sender is None:
            return await ctx.send("You need to donate to use this command! <https://paypal.me/akireee>")
        has_role = discord.utils.find(lambda r: r.id == 444294762783178752, sender.roles)
        if has_role is None:
            return await ctx.send("You need to donate to use this command! <https://paypal.me/akireee>")
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        if sensitivity > 85 or sensitivity < 60:
            return await ctx.send("Sensitivity can't be above 85 or below 60.")
        self.bot.perspective[str(ctx.guild.id)] = sensitivity
        f = open(os.path.join(os.getcwd(), 'data', 'perspective.json'), 'w')
        f.write(json.dumps(self.bot.perspective))
        f.close()
        await ctx.send("Successfully set this server's toxicity filter to **{}%**".format(sensitivity))

    @filter.command(aliases=["del", "delete"], pass_context=True)
    async def remove(self, ctx):
        sender = self.bot.get_guild(294215057129340938).get_member(ctx.author.id)
        if sender is None:
            return await ctx.send("You need to donate to use this command! <https://paypal.me/akireee>")
        has_role = discord.utils.find(lambda r: r.id == 444294762783178752, sender.roles)
        if has_role is None:
            return await ctx.send("You need to donate to use this command! <https://paypal.me/akireee>")
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        try:
            del self.bot.perspective[str(ctx.guild.id)]
            f = open(os.path.join(os.getcwd(), 'data', 'perspective.json'), 'w')
            f.write(json.dumps(self.bot.perspective))
            f.close()
        except:
            await ctx.send("No toxicity filter was applied in this server.")
        else:
            await ctx.send("Successfully removed this server's toxicity filter.")

def setup(bot):
    bot.add_cog(Filter(bot))
