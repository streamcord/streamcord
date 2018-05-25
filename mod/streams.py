from discord.ext import commands
from utils.functions import TWAPI_REQUEST
import discord
import logging, traceback

class Streams:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def stream(self, ctx, *, user):
        await ctx.trigger_typing()
        user = user.split('/')[-1]
        e = discord.Embed(color=discord.Color(0x6441A4))
        r = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + user)
        r.raise_for_status()
        if r.json()["data"] == []:
            await self.bot.say("That user doesn't exist or is not online.")
        else:
            r = r.json()["data"][0]
            u = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + user)
            u.raise_for_status()
            u = u.json()["data"][0]
            g = TWAPI_REQUEST("https://api.twitch.tv/helix/games?id=" + r["game_id"])
            g.raise_for_status()
            g = g.json()["data"][0]
            e.set_author(icon_url=u["profile_image_url"], name=u["display_name"], url="https://twitch.tv/{}".format(u["login"]))
            e.title = r["title"]
            e.description = """
Playing {2} for {0} viewers
**[Watch on Twitch](https://twitch.tv/{1})** or type `twitch watch {1}`\n
Stream Preview:
    """.format(r["viewer_count"], u["login"], g["name"])
            e.set_image(url=r["thumbnail_url"].format(width="1920", height="1080"))
            await ctx.send(embed=e)

    @commands.command(pass_context=True)
    async def watch(self, ctx, *, user):
        await ctx.trigger_typing()
        user = user.split('/')[-1]
        r = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + user)
        r.raise_for_status()
        if r.json()["data"] == []:
            await ctx.send("That user doesn't exist or is not online.")
        else:
            await ctx.send("**<:twitch:404633403603025921> Live on Twitch**\nhttps://twitch.tv/{}".format(user))

def setup(bot):
    bot.add_cog(Streams(bot))
