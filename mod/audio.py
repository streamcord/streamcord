from discord.ext import commands
import discord, asyncio
import youtube_dl
from utils.functions import TWAPI_REQUEST, DBOTS_REQUEST

class Audio:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def listen(self, ctx, *, url: str):
        """Listen to the specified Twitch user in the current voice channel."""
        if not "https://twitch.tv/" in url:
            url = "https://twitch.tv/" + url

        author = ctx.message.author
        voice_channel = author.voice_channel

        r = DBOTS_REQUEST("/bots/375805687529209857/check?userId=" + str(author.id))
        if r.status_code == 200:
                if not r.json()['voted'] == 1:
                    await self.bot.say(r.json())
                    await self.bot.say("<:twitch:404633403603025921> You need to upvote TwitchBot to listen to streams! Upvote here -> <https://discordbots.org/bot/375805687529209857/vote>")
                    return

        if voice_channel == None:
            await self.bot.say("You need to be in a voice channel!")
            return

        try: vc = await self.bot.join_voice_channel(voice_channel)
        except discord.ClientException:
            session = ctx.message.server.voice_client
            await session.disconnect()
            await asyncio.sleep(2)
            vc = await self.bot.join_voice_channel(voice_channel, ytdl_options={'quiet':True})
        try:
            player = await vc.create_ytdl_player(url)
            player.start()
        except youtube_dl.DownloadError:
            await self.bot.say("<:twitch:404633403603025921> Either that user doesn't exist or they are not online.")
        except: raise
        else:
            r = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + url.split("twitch.tv/")[1])
            r = r.json()["data"][0]
            await self.bot.say("<:twitch:404633403603025921> Now streaming **{}** from <{}> in `{}`! Type `twitch stop` to stop playing this stream.".format(r["title"], url, voice_channel.name))

    @commands.command(pass_context=True, aliases=["stop"])
    async def leave(self, ctx):
        author = ctx.message.author
        vc = author.voice_channel
        session = ctx.message.server.voice_client

        if session == None:
            await self.bot.say("Currently not streaming anything.")
            return
        else:
            await session.disconnect()
            await self.bot.say("Left the voice channel.")

def setup(bot):
    bot.add_cog(Audio(bot))
