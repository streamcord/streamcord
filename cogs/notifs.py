import discord
import traceback, logging
from discord.ext import commands
from utils.functions import TWAPI_REQUEST, SPLIT_EVERY
from utils import settings
import json, re
import os
import aiohttp, asyncio

log = logging.getLogger("bot.notifs")

class Notifs:
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile('^\w+$')

    @commands.group(no_pm=True)
    async def notif(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("View the **`Streamer Notifications`** section under the help command to view usage.")

    @notif.command(no_pm=True)
    async def add(self, ctx, discord_channel: discord.TextChannel = None, twitch_user: str = None, *, msg: str = None):
        """Sets up notifications for a Twitch user in the specified channel."""
        try:
            if not ctx.guild:
                return await ctx.send("You can only use this command in a server.")
            if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
                return await ctx.send("You need the **Manage Server** permission to do this.")
            member = self.bot.get_guild(294215057129340938).get_member(ctx.author.id)
            has_role = False
            if member is not None:
                has_role = discord.utils.find(lambda r: r.id in self.bot.donator_roles, member.roles) is not None # premium role
            if not has_role:
                serv_notifs = []
                for streamer in self.bot.notifs:
                    for cid in self.bot.notifs[streamer].keys():
                        if cid in list(map(lambda c: str(c.id), ctx.guild.channels)):
                            serv_notifs.append(self.bot.notifs[streamer][cid])
                if len(serv_notifs) > 25:
                    return await ctx.send("Hey there! Unfortunately you've reached the maximum amount of notifications that you can add to this server. To add more, you need to donate at <https://twitchbot.io/premium>.")
            s = None
            username = None
            if discord_channel is None:
                await ctx.send("Which channel do you want to receive the notification in? Mention or type the name of one below. *(respond in 60 seconds)*")
                try:
                    m = await self.bot.wait_for('message', check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id, timeout=60)
                    discord_channel = discord.utils.find(lambda c: c.name.lower().startswith(m.clean_content.strip("#").lower()), ctx.guild.text_channels)
                    if discord_channel is None:
                        return await ctx.send("Couldn't find that channel. Exiting command...")
                except asyncio.TimeoutError:
                    return await ctx.send('Response timed out.')
            if twitch_user == None:
                await ctx.send("Type the name of the Twitch channel that you want to set up the notification for. *(respond in 60 seconds)*")
                try:
                    m = await self.bot.wait_for('message', check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id, timeout=60)
                    username = m.content.split('/')[-1]
                    s = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + username)
                    if s.status_code == 404:
                        return await ctx.send("That Twitch user could not be found. Exiting command...")
                    elif "data" not in s.json().keys() or s.status_code > 399:
                        return await ctx.send('Invalid data was sent from Twitch. Exiting command...')
                except asyncio.TimeoutError:
                    return await ctx.send('Response timed out.')
            else:
                username = twitch_user.split('/')[-1]
                s = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + username)
                if s.status_code == 404:
                    return await ctx.send("That Twitch user could not be found. Exiting command...")
            try:
                s = s.json()['data'][0]
            except KeyError:
                return await ctx.send('Invalid data was sent from Twitch. Exiting command...')
            except IndexError:
                return await ctx.send('That Twitch user could not be found. Exiting command...')
            if self.regex.match(username) is None:
                return await ctx.send("That doesn't look like a valid Twitch user. You can only include underscores, letters, and numbers.")
            if msg == None:
                await ctx.send("Enter a custom message that you want to be shown when the user goes live, or type `default` for the default message. *(respond in 180 seconds)*")
                try:
                    m = await self.bot.wait_for('message', check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id, timeout=180)
                    if m.content == 'default' or m.content.lower() == '`default`':
                        msg = '<https://twitch.tv/{}> is now live on Twitch!'.format(username)
                    else:
                        msg = m.content
                except asyncio.TimeoutError:
                    return await ctx.send('Response timed out.')
            try:
                if self.bot.notifs.get(s['id']) is None:
                    self.bot.notifs[s['id']] = {str(discord_channel.id): {"name": username, "last_stream_id": None, "message": msg}}
                else:
                    self.bot.notifs[s['id']][str(discord_channel.id)] = {"name": username, "last_stream_id": None, "message": msg}
                f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
                f.write(json.dumps(self.bot.notifs))
                f.close()
                return await ctx.send('Successfully added notification.')
            except KeyError as e:
                return await ctx.send("That Twitch user doesn't exist. Make sure that you're not putting <> around the name, and that you're not @mentioning a Discord user.")
            except IndexError as e:
                return await ctx.send("That Twitch user doesn't exist. Make sure that you're not putting <> around the name, and that you're not @mentioning a Discord user.")
        except:
            await ctx.send(traceback.format_exc())

    @notif.command(no_pm=True)
    async def list(self, ctx, channel: discord.TextChannel = None):
        """Lists notifications in the current channel."""
        if not ctx.guild:
            return await ctx.send("You can only use this command in a server.")
        if channel is None:
            channel = ctx.channel
        f = list(filter(lambda s: str(channel.id) in list(s.keys()), list(self.bot.notifs.values())))
        e = discord.Embed(color=discord.Color(0x6441A4), title="Streamer notifications for **#{}**".format(channel.name), description="There are {} streamer notification(s) set up for {}".format(len(f), channel.name))
        msg = ""
        for streamer in f:
            s = streamer[str(channel.id)]
            msg += "**{}** - {}\n".format(s.get('name', '???'), s['message'])
        if len(msg) > 1024:
            msg = ""
            e.description += "\nCustom messages weren't included in the embed because there is a Discord-set limit of 1024 characters in a section. They'll still show when the user goes live."
            for streamer in f:
                s = streamer[str(channel.id)]
                msg += "{}, ".format(s.get('name', '???'))
        e.add_field(name="Notifications", value=msg[:1024] or 'No streamer notifications are set up for this channel.')
        e.set_footer(icon_url=ctx.guild.icon_url, text=ctx.guild.name)
        await ctx.send(embed=e)

    @notif.command(aliases=["del", "delete"], no_pm=True)
    async def remove(self, ctx, discord_channel: discord.TextChannel, twitch_user: str):
        """Deletes notifications for a Twitch user in the specified channel."""
        if not ctx.guild:
            return await ctx.send("You can only use this command in a server.")
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
    async def formatting(self, ctx):
        e = discord.Embed(color=discord.Color(0x6441A4), title="Notification message variables")
        e.description = """
Use one of the variables below to insert data into a stream notification message.

*`$title$`* - The stream's title
*`$viewers$`* - The number of people currently watching the stream
*`$game$`* - The game that the streamer is currently playing
*`$url$`* - The channel's URL
*`$name$`* - The channel's name
*`$everyone$`* - Inserts an @everyone mention
*`$here$`* - Inserts an @here mention
"""
        e.set_footer(icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url, text=str(ctx.author))
        await ctx.send(embed=e)

    @notif.command(no_pm=True)
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
