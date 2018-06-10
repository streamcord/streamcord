import discord
from discord.ext import commands
import os, os.path
import json

class LiveCheck:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def live_check(self, ctx, *, role = None):
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        if role is None:
            try:
                del self.bot.livecheck[str(ctx.guild.id)]
                f = open(os.path.join(os.getcwd(), 'data', 'live.json'), 'w')
                f.write(json.dumps(self.bot.livecheck))
                f.close()
            except KeyError as e:
                return await ctx.send("No live check has been set up for this server. To add live checking, type `twitch live_check role`.")
            except:
                raise
            else:
                return await ctx.send("Removed live checking from this server.")
        else:
            role_to_add = discord.utils.find(lambda r: r.name == role, ctx.guild.roles)
            if role_to_add is None:
                return ctx.send("Could not find a role with the name `{}`. Make sure to only enter the role's name, and not the @mention.".format(role))
            self.bot.livecheck[str(ctx.guild.id)] = role_to_add.id
            f = open(os.path.join(os.getcwd(), 'data', 'live.json'), 'w')
            f.write(json.dumps(self.bot.livecheck))
            f.close()
            await ctx.send("Users in this server who go live on Twitch will receive the `{}` role.".format(role_to_add.name))
            g = ctx.guild
            for m in filter(lambda m: isinstance(m.activity, discord.Streaming), g.members):
                if not m.bot:
                    log.info("Adding streamer role to {before.id} in {before.guild.id}".format(before=m))
                    await m.add_roles(role_to_add, reason="User went live on Twitch")
            for m in filter(lambda m: discord.utils.get(m.roles, id=role_to_add.id) is not None, g.members):
                if not isinstance(m.activity, discord.Streaming):
                    if not m.bot:
                        log.info("Removing streamer role from {before.id} in {before.guild.id}".format(before=m))
                        await m.remove_roles(role_to_add, reason="User no longer live on Twitch")


def setup(bot):
    bot.add_cog(LiveCheck(bot))
