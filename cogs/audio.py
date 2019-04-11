from discord.ext import commands
import discord, asyncio
import youtube_dl
import logging, traceback
import requests
from utils import settings, lang, http
import datadog
import secrets

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
    def __init__(self, source, *, data, volume=1):
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

class Audio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, no_pm=True)
    async def listen(self, ctx, *, url: str):
        """Listen to the specified Twitch user in the current voice channel."""
        msgs = await lang.get_lang(ctx)
        url = "https://www.twitch.tv/" + url.split('/')[-1]
        if (not hasattr(ctx.author, "voice")) or ctx.author.voice is None:
            return await ctx.send(msgs['audio']['author_not_in_voice_channel'])
        voice_channel = ctx.author.voice.channel
        prem_check = requests.get(f"https://api.twitchbot.io/premium/{ctx.author.id}", headers={"X-Auth-Key": settings.DashboardKey})
        if prem_check.json().get('premium') != True or prem_check.status_code != 200:
            r = requests.get(f"https://dash.twitchbot.io/api/users/{ctx.author.id}/votes", headers={"X-Auth-Key": settings.DashboardKey})
            if r.status_code != 200 or r.json()['active'] == False:
                # Fallback in case the dashboard failed
                r = http.BotLists.DBLRequest(f"/bots/375805687529209857/check?userId={ctx.author.id}")
                if r.status_code == 200 and not r.json()['voted'] == 1:
                    return await ctx.send(embed=lang.EmbedBuilder(msgs['audio']['need_upvote_to_continue']))
        m = await ctx.send(msgs['audio']['please_wait'])
        try:
            try:
                channel = await voice_channel.connect()
            except discord.ClientException:
                session = ctx.message.guild.voice_client
                await session.disconnect()
                await asyncio.sleep(2)
                channel = await voice_channel.connect()
        except Exception as ex:
            return await ctx.send(f"A {type(ex).__name__} occurred: {ex}")
        try:
            r = http.TwitchAPIRequest("https://api.twitch.tv/helix/streams?user_login=" + url.split("twitch.tv/")[1])
            if len(r.json()["data"]) < 1:
                return await m.edit(content=msgs['audio']['user_does_not_exist_or_not_streaming'])
            r = r.json()["data"][0]
            r2 = http.TwitchAPIRequest("https://api.twitch.tv/helix/users?login=" + url.split("twitch.tv/")[1])
            if len(r2.json()["data"]) < 1:
                return await m.edit(content=msgs['audio']['user_does_not_exist_or_not_streaming'])
            r2 = r2.json()["data"][0]
            e = discord.Embed(color=0x6441A4, title=msgs['audio']['now_playing']['title'].format(channel=voice_channel.name), description=msgs['audio']['now_playing']['description'].format(title=r['title'], viewer_count=r['viewer_count']))
            e.set_author(name=r2['display_name'], url=url, icon_url=r2['profile_image_url'])
            e.set_image(url=r['thumbnail_url'].format(width=1920, height=1080) + f"?{secrets.token_urlsafe(5)}")
            e.set_footer(icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url, text=f"{ctx.author} - {msgs['audio']['now_playing']['footer']}")
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            channel.play(player, after=lambda e: logging.error("{}: {}".format(type(e).__name__, e)) if e else None)
            self.bot.active_vc[ctx.message.guild.id] = e
            await m.edit(content=None, embed=e)
        except youtube_dl.DownloadError:
            await ctx.send(msgs['audio']['user_does_not_exist_or_not_streaming'])
        except TimeoutError:
            await ctx.send(msgs['audio']['connection_timeout'])
        except discord.ClientException as ex:
            await ctx.send(f"{type(ex).__name__}: {ex}")
            #await ctx.send("I'm already in a voice channel. Please stop the existing stream and then start it in the new channel.")
        except:
            raise

    @commands.command(aliases=["stop"], no_pm=True)
    async def leave(self, ctx):
        msgs = await lang.get_lang(ctx)
        session = ctx.message.guild.voice_client
        if session == None:
            await ctx.send(msgs['audio']['not_streaming'])
            return
        else:
            await session.disconnect()
            try:
                del self.bot.active_vc[ctx.message.guild.id]
            except:
                pass
            await ctx.send(msgs['audio']['disconnected'])

    @commands.command(pass_context=True, aliases=['playing', 'nowplaying'])
    async def np(self, ctx):
        msgs = await lang.get_lang(ctx)
        player_embed = self.bot.active_vc.get(ctx.message.guild.id)
        if player_embed is None:
            await ctx.send(msgs['audio']['not_streaming'])
        else:
            player_embed.title = msgs['audio']['now_playing']['title'].format(channel=ctx.author.voice.channel.name)
            await ctx.send(embed=player_embed)


def setup(bot):
    bot.add_cog(Audio(bot))
