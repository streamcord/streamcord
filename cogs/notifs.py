import discord
import traceback
from discord.ext import commands
from utils.functions import TWAPI_REQUEST, STREAM_REQUEST, SPLIT_EVERY
from utils import settings
import json
import os
import aiohttp

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

class StreamNotifs:
    def __init__(self, bot):
        self.bot = bot
        self.game_cache = {}

    async def poll(self):
        await bot.wait_until_ready()
        while not bot.is_closed():
            ids_to_fetch = SPLIT_EVERY(100, self.bot.notifs)
            for split in ids_to_fetch:
                r = STREAM_REQUEST("https://api.twitch.tv/helix/streams?user_id=" + list(split.keys()).join("&user_id="))
                if r.status_code > 299:
                    TRIGGER_WEBHOOK("Stream request returned non-2xx status code: {}\n```json\n{}\n```".format(r.status_code, r.json()))
                    continue
                for stream in r.json()['data']:
                    meta = self.bot.notifs[stream['user_id']]
                    if stream['type'] == 'live':
                        for channel_id in meta.keys():
                            obj = meta[channel_id]
                            if not obj['last_stream_id'] == stream['id']:
                                self.bot.notifs[stream['user_id']][channel_id]['last_stream_id'] = stream['id']
                                e = discord.Embed(color=discord.Color(0x6441A4))
                                e.title = stream['title']
                                game = "null"
                                if self.game_cache.get(stream['game_id']) is None:
                                    r2 = STREAM_REQUEST("https://api.twitch.tv/helix/games?id=" + stream['game_id'])
                                    if r2.status_code > 299:
                                        TRIGGER_WEBHOOK("Stream request returned non-2xx status code: {}\n```json\n{}\n```".format(r2.status_code, r2.json()))
                                    else:
                                        game = r2.json()['data'][0]['name']
                                        self.game_cache[stream['game_id']] = game
                                else:
                                    game = self.game_cache[stream['game_id']]
                                e.description = "Playing {} for {} viewers".format(game, stream['viewer_count'])
                                e.set_image(url=stream['thumbnail_url'].format(width=1920, height=1080))
                                try:
                                    await self.bot.get_channel(channel_id).send(obj['message'], embed=e)
                                    await asyncio.sleep(1)
                                except discord.Forbidden:
                                    pass
                                except:
                                    TRIGGER_WEBHOOK("Failed to send message: ```\n{}\n```".format(traceback.format_exc()))
                    await asyncio.sleep(2)
            await asyncio.sleep(240)

def setup(bot):
    bot.add_cog(Notifs(bot))
    bot.loop.create_task(StreamNotifs(bot).poll)
