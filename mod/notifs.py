import discord
import traceback
from discord.ext import commands
from utils.functions import TWAPI_REQUEST
import json
import os

class Notifs:
    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True)
    async def notif(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.bot.say("Type `twitch help notif` to view command usage.")

    @notif.command(pass_context=True)
    @commands.has_permissions(manage_server=True)
    async def add(self, ctx, discord_channel: discord.Channel, *, twitch_users: str):
        """Sets up notifications for a Twitch user in the specified channel."""
        username = twitch_users
        if "https://twitch.tv/" in twitch_users:
            username = twitch_users.strip("https://twitch.tv").strip("/")
        username = username.strip(" ").split(",")
        for u in username:
            if u.startswith("--"):
                if u.startswith("--game="):
                    game = u.split("=", 1)
            else:
                try:
                    await self.bot.send_typing(ctx.message.channel)
                    s = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + u)
                    if s.status_code == 404:
                        await self.bot.say("That user does not exist.")
                    else:
                        if self.bot.notifs.get(s.json()['data'][0]['id']) is None:
                            self.bot.notifs[s.json()['data'][0]['id']] = {discord_channel.id: True}
                        else:
                            self.bot.notifs[s.json()['data'][0]['id']][discord_channel.id] = True
                        f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
                        f.write(json.dumps(self.bot.notifs))
                        f.close()
                        if len(username) == 1:
                            await self.bot.say("You should now receive a message in {} when `{}` goes live.".format(discord_channel.mention, u))
                except:
                    await self.bot.say(traceback.format_exc())
        if len(u) > 1:
            await self.bot.say("You should now receive a message in {} when those channels go live.".format(discord_channel.mention))

    @notif.command(aliases=["del", "delete"], pass_context=True)
    @commands.has_permissions(manage_server=True)
    async def remove(self, ctx, discord_channel: discord.Channel, twitch_user: str):
        """Deletes notifications for a Twitch user in the specified channel."""
        username = twitch_user
        if "https://twitch.tv/" in twitch_user:
            username = twitch_user.strip("https://twitch.tv").strip("/")
        try:
            s = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + username)
            if s.status_code == 404:
                await self.bot.say("That user does not exist.")
            else:
                del self.bot.notifs[s.json()['data'][0]['id']][discord_channel.id]
                if len(self.bot.notifs[s.json()['data'][0]['id']]) == 0:
                    del self.bot.notifs[s.json()['data'][0]['id']]
                f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
                f.write(json.dumps(self.bot.notifs))
                f.close()
        except KeyError:
            await self.bot.say("Either that user doesn't exist or is not set up for that channel. kthx")
        except:
            await self.bot.say(traceback.format_exc())
        else:
            await self.bot.say("You won't get any notifications in {} when `{}` goes live.".format(discord_channel.mention, username))

def setup(bot):
    bot.add_cog(Notifs(bot))
