from discord.ext import commands
import discord, asyncio
import youtube_dl
import logging
from utils.functions import TWAPI_REQUEST, DBOTS_REQUEST

class Audio:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def listen(self, ctx, *, url: str):
        """Listen to the specified Twitch user in the current voice channel."""
        url = "https://www.twitch.tv/" + url.split('/')[-1]
        author = ctx.message.author
        voice_channel = author.voice_channel

        r = DBOTS_REQUEST("/bots/375805687529209857/check?userId=" + str(author.id))
        if r.status_code == 200 and not r.json()['voted'] == 1:
                await self.bot.say("<:twitch:404633403603025921> You need to upvote TwitchBot to listen to streams! Upvote here -> <https://discordbots.org/bot/375805687529209857/vote>. If you just upvoted, please allow up to 5 minutes for the upvote to process.")
                return

        if voice_channel == None:
            await self.bot.say("You need to be in a voice channel!")
            return

        m = await ctx.send("Please wait... <a:loading:414007832849940482>")
        try: vc = await self.bot.join_voice_channel(voice_channel)
        except discord.ClientException:
            session = ctx.message.guild.voice_client
            await session.disconnect()
            await asyncio.sleep(2)
            vc = await self.bot.join_voice_channel(voice_channel)
        try:
            r = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + url.split("twitch.tv/")[1])
            r = r.json()["data"][0]
            await asyncio.sleep(0.5)
            r2 = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + url.split("twitch.tv/")[1])
            r2 = r2.json()["data"][0]
            e = discord.Embed(color=0x6441A4, title="Now playing in {}".format(voice_channel.name), description="**{}**\n{} currently watching".format(r['title'], r['viewer_count']))
            e.set_author(name=r2['display_name'], url=url, icon_url=r2['profile_image_url'])
            e.set_image(url=r['thumbnail_url'].format(width=1920, height=1080))
            player = await vc.create_ytdl_player(url, ytdl_options={'quiet':False})
            player.start()
            self.bot.vc[ctx.message.server.id] = e
            await m.delete()
            await ctx.send(embed=e)
        except youtube_dl.DownloadError:
            await ctx.send("<:twitch:404633403603025921> Either that user doesn't exist or they are not online.")
        except:
            await ctx.send(traceback.format_exc())

    @commands.command(pass_context=True, aliases=["stop"])
    async def leave(self, ctx):
        author = ctx.message.author
        vc = author.voice_channel
        session = ctx.message.guild.voice_client

        if session == None:
            await ctx.send("Currently not streaming anything.")
            return
        else:
            await session.disconnect()
            del self.bot.vc[ctx.message.server.id]
            await ctx.send("Left the voice channel.")

    @commands.command(pass_context=True, aliases=['playing', 'nowplaying'])
    async def np(self, ctx):
        vc = self.bot.vc.get(ctx.message.server.id)
        if vc is None:
            await ctx.send("Currently not streaming anything.")
        else:
            vc.title = "Now playing in {}".format(ctx.message.author.voice_channel.name)
            await ctx.send(embed=vc)

def setup(bot):
    bot.add_cog(Audio(bot))
