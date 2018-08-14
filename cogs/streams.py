from discord.ext import commands
from utils.functions import TWAPI_REQUEST
import discord, asyncio
import logging, traceback
from random import choice
import urllib.parse

class Streams:
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def stream(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Type `twitch commands` to view command usage.")

    @stream.command()
    async def user(self, ctx, *, user):
        await ctx.trigger_typing()
        user = user.split('/')[-1]
        e = discord.Embed(color=discord.Color(0x6441A4))
        r = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + user)
        r.raise_for_status()
        if r.json().get("data") in [[], None]:
            await ctx.send("That user doesn't exist or is not online. Make sure you're only entering the user's name and not anything extra, like `()` or `<>`.")
        else:
            r = r.json()["data"][0]
            u = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + user)
            u.raise_for_status()
            await asyncio.sleep(1)
            u = u.json()["data"][0]
            g = TWAPI_REQUEST("https://api.twitch.tv/helix/games?id=" + r["game_id"])
            g.raise_for_status()
            await asyncio.sleep(1)
            try:
                g = g.json()["data"][0]
            except:
                g = {"id": 0, "name": "Unknown"}
            e.set_author(icon_url=u["profile_image_url"], name=u["display_name"], url="https://twitch.tv/{}".format(u["login"]))
            e.title = r["title"]
            e.description = """
Playing {2} for {0} viewers
**[Watch on Twitch](https://twitch.tv/{1})** or type `twitch watch {1}`\n
Stream Preview:
    """.format(r["viewer_count"], u["login"], g["name"])
            e.set_image(url=r["thumbnail_url"].format(width="1920", height="1080"))
            await ctx.send(embed=e)

    @stream.command()
    async def watch(self, ctx, *, user):
        await ctx.trigger_typing()
        user = user.split('/')[-1]
        r = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + user)
        r.raise_for_status()
        if r.json()["data"] == []:
            await ctx.send("That user doesn't exist or is not online.")
        else:
            await ctx.send("**<:twitch:404633403603025921> Live on Twitch**\nhttps://twitch.tv/{}".format(user))

    @stream.command()
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def game(self, ctx, *, name):
        await ctx.trigger_typing()
        g = TWAPI_REQUEST("https://api.twitch.tv/helix/games?" + urllib.parse.urlencode({"name": name}))
        g.raise_for_status()
        try:
            g = g.json()['data'][0]
        except:
            return await ctx.send("That game could not be found.")
        game = g['name']
        await asyncio.sleep(1)
        s = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?game_id=" + g['id'])
        s.raise_for_status()
        if len(s.json()['data']) < 1:
            return await ctx.send("Nobody is streaming that game.")
        stream = choice(s.json()['data'])
        await asyncio.sleep(1)
        u = TWAPI_REQUEST("https://api.twitch.tv/helix/users?id=" + stream['user_id'])
        u.raise_for_status()
        await ctx.send("Check out {0} playing {1} for {2} viewers:\nhttps://twitch.tv/{0}".format(u.json()['data'][0]['display_name'], game, stream['viewer_count']))


    @stream.command()
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def top(self, ctx):
        await ctx.trigger_typing()
        r = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?first=20")
        r.raise_for_status()
        stream = choice(r.json()['data'])
        u = TWAPI_REQUEST("https://api.twitch.tv/helix/users?id=" + stream['user_id'])
        u.raise_for_status()
        await asyncio.sleep(1)
        u = u.json()["data"][0]
        g = TWAPI_REQUEST("https://api.twitch.tv/helix/games?id=" + stream["game_id"])
        g.raise_for_status()
        await asyncio.sleep(1)
        g = g.json()["data"][0]
        return await ctx.send("Check out {0} playing {1} for {2} viewers:\nhttps://twitch.tv/{0}".format(u['login'], g['name'], stream['viewer_count']))



def setup(bot):
    bot.add_cog(Streams(bot))
