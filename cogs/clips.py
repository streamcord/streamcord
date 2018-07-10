from discord.ext import commands
import discord
from utils.functions import TWAPI_REQUEST
from urllib.parse import urlencode
from random import choice
import asyncio
import logging
import re

class Clips:
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile('^\w+$')

    @commands.group(pass_context=True, aliases=["clip"])
    async def clips(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Type `twitch help clips` to view command usage.")

    @clips.command(pass_context=True, name="from", aliases=["channel"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def _from(self, ctx, twitch_user: str, *args):
        twitch_user = twitch_user.split('/')[-1]
        if self.regex.match(twitch_user) is None:
            return await ctx.send("That doesn't look like a valid Twitch user. You can only include underscores, letters, and numbers.")
        trending = ""
        if "--trending" in args:
            trending = "&trending=true"
        await ctx.trigger_typing()
        r = TWAPI_REQUEST("https://api.twitch.tv/kraken/clips/top?channel=" + twitch_user + trending)
        if r.status_code != 200:
            await ctx.send("An error Occurred: {}".format(r.status_code))
        elif len(r.json()['clips']) < 1:
            await ctx.send("No clips found for that user.")
            return
        else:
            clip = choice(r.json()['clips'])
            await ctx.send("Check out {} playing {}:\n{}".format(clip['broadcaster']['display_name'], clip['game'], clip['url'].split('?')[0]))

    @clips.command(pass_context=True, aliases=["popular", "top"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def trending(self, ctx):
        await ctx.trigger_typing()
        r = TWAPI_REQUEST("https://api.twitch.tv/kraken/clips/top")
        if r.status_code != 200:
            await ctx.send("An error Occurred: {}".format(r.status_code))
        elif len(r.json()['clips']) < 1:
            await ctx.send("No clips found.")
            return
        else:
            clip = choice(r.json()['clips'])
            await ctx.send("Check out {} playing {}:\n{}".format(clip['broadcaster']['display_name'], clip['game'], clip['url'].split('?')[0]))

    @clips.command(pass_context=True, aliases=["playing"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def game(self, ctx, *, game):
        await ctx.trigger_typing()
        trending = ""
        if game.endswith(" --trending"):
            trending = "&trending=true"
        r = TWAPI_REQUEST("https://api.twitch.tv/kraken/search/games?" + urlencode({"query": game.strip(' --trending')}))
        if r.status_code != 200:
            await ctx.send("An error Occurred: {}-1".format(r.status_code))
            return
        elif len(r.json()['games']) < 1:
            await ctx.send("No clips found for that game.")
            return
        game = r.json()['games'][0]['name']
        await asyncio.sleep(1)
        r = TWAPI_REQUEST("https://api.twitch.tv/kraken/clips/top?" + urlencode({"game": game}) + trending)
        if r.status_code != 200:
            await ctx.send("An error Occurred: {}-2".format(r.status_code))
            return
        elif len(r.json()['clips']) < 1:
            await ctx.send("No clips found for that game.")
            return
        clip = choice(r.json()['clips'])
        await ctx.send("Check out {} playing {}:\n{}".format(clip['broadcaster']['display_name'], clip['game'], clip['url'].split('?')[0]))


def setup(bot):
    bot.add_cog(Clips(bot))
