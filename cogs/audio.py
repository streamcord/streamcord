from discord.ext import commands
import discord, asyncio
import youtube_dl
import logging, traceback
from utils.functions import TWAPI_REQUEST, DBOTS_REQUEST


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': False,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': True,
    'quiet': False,
    'no_warnings': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'before_options': '-nostdin',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Audio:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def listen(self, ctx, *, url: str):
        """Listen to the specified Twitch user in the current voice channel."""
        url = "https://www.twitch.tv/" + url.split('/')[-1]
        author = ctx.message.author
        if author.voice is None:
            return await ctx.send("You need to be in a voice channel!")
        voice_channel = author.voice.channel
        member = self.bot.get_guild(294215057129340938).get_member(ctx.author.id)
        has_role = False
        if member is not None:
            has_role = discord.utils.find(lambda r: r.id == 460491951729278988, member.roles) is not None # gold patron role
        if not has_role:
            r = DBOTS_REQUEST("/bots/375805687529209857/check?userId=" + str(author.id))
            if r.status_code == 200 and not r.json()['voted'] == 1:
                await ctx.send("<:twitch:404633403603025921> You need to upvote TwitchBot to listen to streams! Upvote here -> <https://discordbots.org/bot/375805687529209857/vote>. If you just upvoted, please allow up to 5 minutes for the upvote to process.\n**Want to skip upvoting?** You can become a patron at <https://patreon.com/devakira> to listen without upvoting.")
                return

        m = await ctx.send("Please wait... <a:loading:414007832849940482>")
        try: vc = await voice_channel.connect()
        except discord.ClientException:
            session = ctx.message.guild.voice_client
            await session.disconnect()
            await asyncio.sleep(2)
            vc = await voice_channel.connect()
        try:
            r = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + url.split("twitch.tv/")[1])
            if len(r.json()["data"]) < 1:
                await m.delete()
                return await ctx.send("<:twitch:404633403603025921> This user doesn't exist or is not currently streaming. If you entered the channel's url, try again with just the name.")
            r = r.json()["data"][0]
            await asyncio.sleep(0.5)
            r2 = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + url.split("twitch.tv/")[1])
            if len(r2.json()["data"]) < 1:
                await m.delete()
                return await ctx.send("<:twitch:404633403603025921> This user doesn't exist or is not currently streaming. If you entered the channel's url, try again with just the name.")
            r2 = r2.json()["data"][0]
            e = discord.Embed(color=0x6441A4, title="Now playing in {}".format(voice_channel.name), description="**{}**\n{} currently watching".format(r['title'], r['viewer_count']))
            e.set_author(name=r2['display_name'], url=url, icon_url=r2['profile_image_url'])
            e.set_image(url=r['thumbnail_url'].format(width=1920, height=1080))
            e.set_footer(icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url, text=str(ctx.author) + " - Type 'twitch leave' to stop the stream")
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            vc.play(player, after=lambda e: logging.error("An audio player error occurred: " + e) if e else None)
            self.bot.vc[ctx.message.guild.id] = e
            await m.delete()
            await ctx.send(embed=e)
        except youtube_dl.DownloadError:
            await ctx.send("<:twitch:404633403603025921> This user doesn't exist or is not currently streaming.")
        except:
            await ctx.send("A fatal exception occurred:\n```\n" + traceback.format_exc() + "\n```")

    @commands.command(pass_context=True, aliases=["stop"])
    async def leave(self, ctx):
        session = ctx.message.guild.voice_client

        if session == None:
            await ctx.send("Currently not streaming anything.")
            return
        else:
            await session.disconnect()
            del self.bot.vc[ctx.message.guild.id]
            await ctx.send("Left the voice channel.")

    @commands.command(pass_context=True, aliases=['playing', 'nowplaying'])
    async def np(self, ctx):
        vc = self.bot.vc.get(ctx.message.guild.id)
        if vc is None:
            await ctx.send("Currently not streaming anything.")
        else:
            vc.title = "Now playing in {}".format(ctx.message.author.voice.channel.name)
            await ctx.send(embed=vc)

def setup(bot):
    bot.add_cog(Audio(bot))
