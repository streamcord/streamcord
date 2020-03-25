import time

import discord
from discord.ext import commands
from ..utils import lang


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def game(self, ctx, *, name):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        e = discord.Embed(color=discord.Color(0x6441A4))
        r = await self.bot.chttp_twitch.get('/games', params={'name': name})
        r.raise_for_status()
        try:
            r = (await r.json())['data'][0]
        except IndexError:
            return await ctx.send(msgs['games']['no_results'])
        e.title = r["name"]
        link = f"https://www.twitch.tv/directory/game/{r['name'].replace(' ', '%20')}"
        e.description = f"[{msgs['games']['view_streams']}]({link})"
        e.set_thumbnail(url=r["box_art_url"].format(width=285, height=380))

        r2 = await self.bot.chttp.search_game_igdb(name)
        rjson = await r2.json()
        if r2.status != 200 or not rjson:
            e.add_field(
                name=msgs['games']['game_details_title'],
                value=msgs['games']['igdb_fetch_error'].format(error=r2.status)
            )
            e.set_footer(text=msgs['games']['game_id'].format(id=r['id']))
        else:
            rjson = rjson[0]
            summary = rjson['summary'][:1000]
            if len(summary) == 1000:
                summary += f"... {msgs['games']['info_cutoff']}"
            if rating := rjson.get('rating'):
                ratings = round(rating/10, 1)
                if ratings > 5:
                    rate_emoji = "\\👍"
                else:
                    rate_emoji = "\\👎"
                e.add_field(
                    name=msgs['games']['game_rating']['name'],
                    value=msgs['games']['game_rating']['value'].format(
                        emoji=rate_emoji,
                        score=ratings,
                        count=rjson.get('rating_count', 0)))
            if release := rjson.get('first_release_date'):
                e.add_field(
                    name=msgs['games']['release_date'],
                    value=time.strftime('%B %d, %Y', time.gmtime(release)))
            e.add_field(
                name=msgs['games']['game_desc'],
                value=summary,
                inline=False)
            link = f"https://igdb.com/games/{rjson['slug']}"
            e.description += f" • [{msgs['games']['view_on_igdb']}]({link})"
            e.set_footer(
                text=f"{msgs['games']['game_id'].format(id=r['id'])} • IGDB ID: {rjson['id']}")
        await ctx.send(embed=e)

    @commands.command(pass_context=True)
    async def top(self, ctx):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        e = discord.Embed(color=discord.Color(0x6441A4), title=msgs['games']['top_games'])
        r = await self.bot.chttp_twitch.get('/games/top', params={'limit': 10}, is_v5=True)
        r.raise_for_status()
        r = (await r.json())['top']
        place = 1
        for game in r:
            e.add_field(
                inline=False,
                name=f"`{place}.` {game['game']['name']}",
                value=msgs['games']['top_games_desc'].format(
                    view_count=game['viewers'],
                    channel_count=game['channels']))
            place += 1
        await ctx.send(embed=e)


class GameStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['ow', 'fn', 'fortnite'])
    async def overwatch(self, ctx):
        msgs = await lang.get_lang(ctx)
        await ctx.send(msgs['games']['removal_notice'])

def setup(bot):
    bot.add_cog(Games(bot))
    bot.add_cog(GameStats(bot))
