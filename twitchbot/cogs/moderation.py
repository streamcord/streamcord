import asyncio
import os

import discord
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ban(self, ctx, user: discord.Member, *, reason="No reason specified."):
        if not ctx.guild:
            return await ctx.send("You can't run this command in direct messages.")
        if not ctx.author.permissions_in(ctx.channel).ban_members:
            return await ctx.send("You need the **Ban Members** permission to do this!")
        try:
            await user.ban(reason=f"Responsible moderator: {ctx.author}\nReason: {reason}")
        except discord.Forbidden:
            return await ctx.send("I need the **Ban Members** permission to do this!")
        except Exception:
            return await ctx.send("That member couldn't be banned. Do they have a higher role than me?")
        else:
            return await ctx.send(f"Successfully banned **{user}** for reason **{reason}**")

    @commands.command()
    async def kick(self, ctx, user: discord.Member, *, reason="No reason specified."):
        if not ctx.guild:
            return await ctx.send("You can't run this command in direct messages.")
        if not ctx.author.permissions_in(ctx.channel).kick_members:
            return await ctx.send("You need the **Kick Members** permission to do this!")
        try:
            await user.kick(reason=f"Responsible moderator: {ctx.author}\nReason: {reason}")
        except discord.Forbidden:
            return await ctx.send("I need the **Kick Members** permission to do this!")
        except Exception:
            return await ctx.send("That member couldn't be kicked. Do they have a higher role than me?")
        else:
            return await ctx.send(f"Successfully kicked **{user}** for reason **{reason}**")

    @commands.command(aliases=["clear", "prune"])
    async def purge(self, ctx, amt: int):
        if not ctx.guild:
            return await ctx.send("You can't run this command in direct messages.")
        if not ctx.author.permissions_in(ctx.channel).manage_messages:
            return await ctx.send("You need the **Manage Messages** permission to do this!")
        if amt > 99 or amt < 2:
            return await ctx.send("You can't delete more than 99 messages or less than 2.")
        try:
            await ctx.channel.purge(limit=amt + 1, check=lambda m: m.guild is not None)
        except discord.Forbidden:
            return await ctx.send("I need the **Manage Messages** permission to do this!")
        else:
            m = ctx.send("Deleted {} messages.".format(amt))
            await asyncio.sleep(3)
            try:
                await m.delete()
            except Exception:
                pass

def setup(bot):
    if os.getenv('ENABLE_PRO_FEATURES') == '1':
        bot.add_cog(Moderation(bot))
