from discord.ext import commands
import discord
from utils.functions import TWAPI_REQUEST

# NOTE: This cog uses the v5 version of the Twitch API.

class Games:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def game(self, ctx, *, name):
        await ctx.trigger_typing()
        e = discord.Embed(color=discord.Color(0x6441A4))
        r = TWAPI_REQUEST("https://api.twitch.tv/helix/games/?name=" + name)
        r.raise_for_status()
        try:
            r = r.json()["data"][0]
        except IndexError:
            return await ctx.send("No results found.")
        e.description = "[View Streams](https://www.twitch.tv/directory/game/{})".format(r["name"].replace(' ', '%20'))
        e.title = r["name"]
        e.set_image(url=r["box_art_url"].format(width=285, height=380))
        await ctx.send(embed=e)

    @commands.command(pass_context=True)
    async def top(self, ctx, cnt: int = 10):
        await ctx.trigger_typing()
        e = discord.Embed(color=discord.Color(0x6441A4), title="<:twitch:404633403603025921> Top Games")
        r = TWAPI_REQUEST("https://api.twitch.tv/kraken/games/top?limit=10")
        r.raise_for_status()
        r = r.json()["top"]
        place = 1
        for game in r:
            e.add_field(inline=False, name="`{}.` {}".format(place, game["game"]["name"]), value="{} viewers • {} channels".format(game["viewers"], game["channels"]))
            place += 1
        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(Games(bot))
