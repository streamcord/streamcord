import discord
import traceback, logging
from discord.ext import commands
from utils.functions import TWAPI_REQUEST, STREAM_REQUEST, SPLIT_EVERY
from utils import settings
import json, re
import os
import aiohttp

log = logging.getLogger("bot.notifs")

class Notifs:
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile('^\w+$')

    @commands.group(pass_context=True)
    async def notif(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("View the **`Streamer Notifications`** section under the help command to view usage.")

    @notif.command(pass_context=True)
    async def add(self, ctx, discord_channel: discord.TextChannel, twitch_user: str, *, msg: str = None):
        """Sets up notifications for a Twitch user in the specified channel."""
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        username = twitch_user.split('/')[-1]
        if self.regex.match(username) is None:
            return await ctx.send("That doesn't look like a valid Twitch user. You can only include underscores, letters, and numbers.")
        if not discord_channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send("I don't have permission to send messages in the requested channel.")
        try:
            await ctx.trigger_typing()
            s = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + username)
            if s.status_code == 404:
                await self.bot.say("That user does not exist.")
            else:
                if self.bot.notifs.get(s.json()['data'][0]['id']) is None:
                    self.bot.notifs[s.json()['data'][0]['id']] = {str(discord_channel.id): {"name": username, "last_stream_id": None, "message": msg or "<https://twitch.tv/{}> is now live on Twitch!".format(username)}}
                else:
                    self.bot.notifs[s.json()['data'][0]['id']][str(discord_channel.id)] = {"name": username, "last_stream_id": None, "message": msg or "<https://twitch.tv/{}> is now live on Twitch!".format(username)}
                f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
                f.write(json.dumps(self.bot.notifs))
                f.close()
                return await ctx.send("You should now receive a message in {} when `{}` goes live.".format(discord_channel.mention, username))
        except KeyError as e:
            return await ctx.send("That Twitch user doesn't exist. Make sure that you're not putting <> around the name, and that you're not @mentioning a Discord user.")
        except IndexError as e:
            return await ctx.send("That Twitch user doesn't exist. Make sure that you're not putting <> around the name, and that you're not @mentioning a Discord user.")
        except:
            return await ctx.send(traceback.format_exc())

    @notif.command()
    async def list(self, ctx, channel: discord.TextChannel = None):
        """Lists notifications in the current channel."""
        if channel is None:
            channel = ctx.channel
        f = list(filter(lambda s: str(channel.id) in list(s.keys()), list(self.bot.notifs.values())))
        e = discord.Embed(color=discord.Color(0x6441A4), title="Streamer notifications for #{}".format(channel.name), description="There are {} streamer notification(s) set up for this channel".format(len(f)))
        msg = ""
        for streamer in f:
            s = streamer[str(channel.id)]
            msg += "**{}** - {}\n".format(s.get('name', '???'), s['message'])
        if len(msg) > 1024:
            msg = ""
            e.description += "\nCustom messages weren't included in the embed because there is a Discord-set limit of 1024 characters in a section. They'll still show when the user goes live."
            for streamer in f:
                s = streamer[str(channel.id)]
                msg += "**{}**\n".format(s.get('name', '???'))
        e.add_field(name="Notifications", value=msg[:1024] or 'No streamer notifications are set up for this channel.')
        e.set_footer(icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url, text=str(ctx.author) + " • Join the support server at discord.me/konomi if the embed did not display correctly")
        await ctx.send(embed=e)

    @notif.command(aliases=["del", "delete"])
    async def remove(self, ctx, discord_channel: discord.TextChannel, twitch_user: str):
        """Deletes notifications for a Twitch user in the specified channel."""
        username = twitch_user.split('/')[-1]
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        if self.regex.match(username) is None:
            return await ctx.send("That doesn't look like a valid Twitch user. You can only include underscores, letters, and numbers.")
        try:
            s = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + username)
            if s.status_code == 404:
                await ctx.send("That user does not exist.")
            else:
                del self.bot.notifs[s.json()['data'][0]['id']][str(discord_channel.id)]
                if len(self.bot.notifs[s.json()['data'][0]['id']]) == 0:
                    del self.bot.notifs[s.json()['data'][0]['id']]
                f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
                f.write(json.dumps(self.bot.notifs))
                f.close()
        except KeyError:
            await ctx.send("Either that user doesn't exist or is not set up for that channel.")
        except:
            await ctx.send(traceback.format_exc())
        else:
            await ctx.send("You won't get any notifications in {} when `{}` goes live.".format(discord_channel.mention, username))

    @notif.command()
    async def force(self, ctx, discord_channel: discord.TextChannel, twitch_user: str):
        """Forces a stream notification for a Twitch user in the specified channel."""
        username = twitch_user.split('/')[-1]
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        elif self.regex.match(username) is None:
            return await ctx.send("That doesn't look like a valid Twitch user. You can only include underscores, letters, and numbers.")
        await ctx.trigger_typing()
        s = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + twitch_user)
        if s.status_code == 404:
            return await ctx.send("That user does not exist.")
        elif len(s.json()['data']) == 0:
            return await ctx.send("That user is not live, can't send a notification for them.")
        s = s.json()
        meta = self.bot.notifs.get(s['data'][0]['user_id'], {}).get(discord_channel.id)
        if meta is None:
            meta = {"last_stream_id": None, "message": "{} is now live on Twitch! <https://twitch.tv/{}>"}


def setup(bot):
    bot.add_cog(Notifs(bot))
