from discord.ext import commands
import discord
from utils.functions import TWAPI_REQUEST
from urllib.parse import urlencode
from random import choice
import asyncio
import logging, traceback
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
        r = TWAPI_REQUEST("https://api.twitch.tv/kraken/clips/top?limit=50&channel=" + twitch_user + trending)
        if r.status_code != 200:
            await ctx.send("An error Occurred: {}".format(r.status_code))
        elif len(r.json()['clips']) < 1:
            await ctx.send("No clips found for that user.")
            return
        else:
            clip = choice(r.json()['clips'])
            m = await ctx.send("Check out {} playing {}:\n{}".format(clip['broadcaster']['display_name'], clip['game'], clip['url'].split('?')[0]))
            if self.bot.clip_votes.get(clip['slug']) is None:
                self.bot.clip_votes[clip['slug']] = {"meta": clip, "votes": []}
            try:
                await m.add_reaction("👍")
            except discord.Forbidden:
                pass

    @clips.command(pass_context=True, aliases=["popular", "top"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def trending(self, ctx):
        await ctx.trigger_typing()
        r = TWAPI_REQUEST("https://api.twitch.tv/kraken/clips/top?limit=50")
        if r.status_code != 200:
            await ctx.send("An error Occurred: {}".format(r.status_code))
        elif len(r.json()['clips']) < 1:
            await ctx.send("No clips found.")
            return
        else:
            clip = choice(r.json()['clips'])
            m = await ctx.send("Check out {} playing {}:\n{}".format(clip['broadcaster']['display_name'], clip['game'], clip['url'].split('?')[0]))
            if self.bot.clip_votes.get(clip['slug']) is None:
                self.bot.clip_votes[clip['slug']] = {"meta": clip, "votes": []}
            try:
                await m.add_reaction("👍")
            except discord.Forbidden:
                pass

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
        elif r.json().get('games') == None:
            return await ctx.send('That game doesn\'t exist.')
        elif len(r.json()['games']) < 1:
            await ctx.send("No clips found for that game.")
            return
        game = r.json()['games'][0]['name']
        r = TWAPI_REQUEST("https://api.twitch.tv/kraken/clips/top?limit=50&" + urlencode({"game": game}) + trending)
        if r.status_code != 200:
            await ctx.send("An error Occurred: {}-2".format(r.status_code))
            return
        elif len(r.json()['clips']) < 1:
            await ctx.send("No clips found for that game.")
            return
        clip = choice(r.json()['clips'])
        m = await ctx.send("Check out {} playing {}:\n{}".format(clip['broadcaster']['display_name'], clip['game'], clip['url'].split('?')[0]))
        if self.bot.clip_votes.get(clip['slug']) is None:
            self.bot.clip_votes[clip['slug']] = {"meta": clip, "votes": []}
        try:
            await m.add_reaction("👍")
        except discord.Forbidden:
            pass

    @clips.command()
    async def uservoted(self, ctx):
        clips = sorted(self.bot.clip_votes, key=lambda c: len(self.bot.clip_votes[c]['votes']))
        try:
            clip = choice(clips[-20:]) # get one of the top 10
        except IndexError:
            return await ctx.send("Nobody has voted on any clips yet. Come back later.")
        clip = self.bot.clip_votes[clip]
        m = await ctx.send("{} votes on this clip by {}:\n{}".format(len(clip['votes']), clip['meta']['broadcaster']['display_name'], clip['meta']['url'].split('?')[0]))
        try:
            await m.add_reaction("👍")
        except discord.Forbidden:
            pass


def setup(bot):
    bot.add_cog(Clips(bot))

    @bot.event
    async def on_reaction_add(reaction, user):
        if not reaction.message.author.id == bot.user.id:
            return
        elif user.bot:
            return
        elif user.id == bot.user.id:
            return
        elif not reaction.emoji == "👍":
            return
        elif not "clips.twitch.tv" in reaction.message.content:
            return
        clip_slug = reaction.message.content.split("\n")[-1].split('/')[-1]
        if str(user.id) in bot.clip_votes[clip_slug]['votes']:
            return
        try:
            bot.clip_votes[clip_slug]['votes'].append(str(user.id))
        except ValueError:
            await reaction.message.channel.send("**{}**, your upvote could\'nt be processed.".format(user.name))

    @bot.event
    async def on_reaction_remove(reaction, user):
        if not reaction.message.author.id == bot.user.id:
            return
        elif user.bot:
            return
        elif user.id == bot.user.id:
            return
        elif not reaction.emoji == "👍":
            return
        elif not "clips.twitch.tv" in reaction.message.content:
            return
        clip_slug = reaction.message.content.split("\n")[-1].split('/')[-1]
        try:
            bot.clip_votes[clip_slug]['votes'].remove(str(user.id))
        except ValueError:
            pass
