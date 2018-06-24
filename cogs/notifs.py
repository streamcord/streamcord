import discord
import traceback
from discord.ext import commands
from utils.functions import TWAPI_REQUEST, STREAM_REQUEST, SPLIT_EVERY
from utils import settings
import aiohttp
import os
import json

class Notifs:
    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True)
    async def notif(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Type `twitch help notif` to view command usage.")

    @notif.command(pass_context=True)
    async def add(self, ctx, discord_channel: discord.TextChannel, twitch_user: str, *, msg: str = None):
        """Sets up notifications for a Twitch user in the specified channel."""
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        username = twitch_user
        if "https://twitch.tv/" in twitch_user:
            username = twitch_user.strip("https://twitch.tv").strip("/")
        try:
            await ctx.trigger_typing()
            s = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + username)
            if s.status_code == 404:
                await self.bot.say("That user does not exist.")
            else:
                if self.bot.notifs.get(s.json()['data'][0]['id']) is None:
                    self.bot.notifs[s.json()['data'][0]['id']] = {str(discord_channel.id): {"last_stream_id": None, "message": msg or "{user} is now live on Twitch!".format(twitch_user)}}
                else:
                    self.bot.notifs[s.json()['data'][0]['id']][str(discord_channel.id)] = {"last_stream_id": None, "message": msg or "{user} is now live on Twitch!".format(twitch_user)}
                f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
                f.write(json.dumps(self.bot.notifs))
                f.close()
                return await ctx.send("You should now receive a message in {} when `{}` goes live.".format(discord_channel.mention, username))
        except KeyError:
            return await ctx.send("That Twitch user doesn't exist. Make sure that you're not putting <> around the name, and that you're not @mentioning a Discord user.")
        except:
            return await ctx.send(traceback.format_exc())

    @notif.command(aliases=["del", "delete"], pass_context=True)
    async def remove(self, ctx, discord_channel: discord.TextChannel, twitch_user: str):
        """Deletes notifications for a Twitch user in the specified channel."""
        username = twitch_user
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send("You need the **Manage Server** permission to do this.")
        if "https://twitch.tv/" in twitch_user:
            username = twitch_user.strip("https://twitch.tv").strip("/")
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

# example streamer object:
# {streamer_id:
#     {discord.TextChannel.id:
#         {"last_stream_id": stream_id,
#         "message": message}
#     }
# }

def setup(bot):
    bot.add_cog(Notifs(bot))
