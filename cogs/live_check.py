import discord
from discord.ext import commands
import os, os.path
import json
import logging

class LiveCheck:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def live_check(self, ctx, *, role = None):
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        if role == "--delete":
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
                return await ctx.send("Successfully removed live checking from this server.")
        elif role is None:
            r = self.bot.livecheck.get(str(ctx.guild.id))
            if r is None:
                return await ctx.send("No live checking is set up for this server. Type `twitch live_check role` to set it up.")
            else:
                return await ctx.send("Live checking is currently set up to give the `{}` role to streamers who go live. If you want to delete live checking, type `twitch live_role delete`.".format(discord.utils.find(lambda n: n.id == r, ctx.guild.roles)))
        else:
            role_to_add = discord.utils.find(lambda r: r.name.lower().startswith(role.lower()), ctx.guild.roles)
            if role_to_add is None:
                return ctx.send("Could not find a role with the name `{}`. Make sure to only enter the role's name, and not the @mention.".format(role))
            self.bot.livecheck[str(ctx.guild.id)] = role_to_add.id
            f = open(os.path.join(os.getcwd(), 'data', 'live.json'), 'w')
            f.write(json.dumps(self.bot.livecheck))
            f.close()
            await ctx.send("Users in this server who go live on Twitch will receive the `{}` role.".format(role_to_add.name))
            g = ctx.guild
            try:
                for m in filter(lambda m: isinstance(m.activity, discord.Streaming), g.members):
                    if not m.bot:
                        logging.info("Adding streamer role to {before.id} in {before.guild.id}".format(before=m))
                        await m.add_roles(role_to_add, reason="User went live on Twitch")
                for m in filter(lambda m: discord.utils.get(m.roles, id=role_to_add.id) is not None, g.members):
                    if not isinstance(m.activity, discord.Streaming):
                        if not m.bot:
                            logging.info("Removing streamer role from {before.id} in {before.guild.id}".format(before=m))
                            await m.remove_roles(role_to_add, reason="User no longer live on Twitch")
            except discord.Forbidden as e:
                await ctx.send("I need the **`Manage Roles`** permission to do this. If I have the permission, then make sure to drag the role named `TwitchBot` above the role you want to live check with.")

    @commands.group(no_pm=True)
    async def live_role(self, ctx):
        if ctx.invoked_subcommand is None:
            e = discord.Embed(color=discord.Color(0x6441A4), title="Live Role - Help", description="With Live Role, you can set up a role to add to users when they go live. TwitchBot will automatically remove the role when the user stops streaming.")
            e.add_field(name="Commands", value="""
`twitch live_role set` - Sets the Live Role for the current server
`twitch live_role delete` - Removes the Live Role configuration
`twitch live_role view` - Tells you which role is currently set up
            """)
            await ctx.send(embed=e)

    @live_role.command()
    async def set(self, ctx, *, role: discord.Role = None):
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        if role is None:
            return await ctx.send("No role was specified. Please re-run the command and @mention a role. For example: `twitch live_role set @Streamers`")
        self.bot.livecheck[str(ctx.guild.id)] = role.id
        f = open(os.path.join(os.getcwd(), 'data', 'live.json'), 'w')
        f.write(json.dumps(self.bot.livecheck))
        f.close()
        await ctx.send("Users in this server who go live on Twitch will receive the `{}` role.".format(role.name))
        g = ctx.guild
        try:
            for m in filter(lambda m: isinstance(m.activity, discord.Streaming), g.members):
                if not m.bot:
                    logging.info("Adding streamer role to {before.id} in {before.guild.id}".format(before=m))
                    await m.add_roles(role, reason="User went live on Twitch")
            for m in filter(lambda m: discord.utils.get(m.roles, id=role.id) is not None, g.members):
                if not isinstance(m.activity, discord.Streaming):
                    if not m.bot:
                        logging.info("Removing streamer role from {before.id} in {before.guild.id}".format(before=m))
                        await m.remove_roles(role, reason="User no longer live on Twitch")
        except discord.Forbidden as e:
            await ctx.send("I need the **`Manage Roles`** permission to do this. If I have the permission, then make sure to drag the role named `TwitchBot` above the role you want to set up.")

    @live_role.command(aliases=['del', 'remove'])
    async def delete(self, ctx):
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        try:
            del self.bot.livecheck[str(ctx.guild.id)]
            f = open(os.path.join(os.getcwd(), 'data', 'live.json'), 'w')
            f.write(json.dumps(self.bot.livecheck))
            f.close()
        except KeyError as e:
            return await ctx.send("No Live Role has been set up for this server. To add a Live Role, type `twitch live_role set @RoleName`.")
        except:
            raise
        else:
            return await ctx.send("Successfully removed the Live Role configuration from this server.")

    @live_role.command(aliases=['list'])
    async def view(self, ctx):
        r = self.bot.livecheck.get(str(ctx.guild.id))
        if r is None:
            return await ctx.send("Live Role is not set up for this server. To set it up, type `twitch live_role set @RoleName`")
        role = discord.utils.find(lambda n: n.id == r, ctx.guild.roles)
        await ctx.send("Live Role is currently set up to give members the **{}** role when they stream.".format(role.name))



def setup(bot):
    bot.add_cog(LiveCheck(bot))
