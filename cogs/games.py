from discord.ext import commands
import discord, asyncio
from utils import lang, http
from utils.functions import FormatOWAPIUser
import logging, traceback
from json import JSONDecodeError
import textwrap
import requests
import time

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    async def game(self, ctx, *, name):
        try:
            await ctx.trigger_typing()
            msgs = await lang.get_lang(ctx)
            e = discord.Embed(color=discord.Color(0x6441A4))
            r = http.TwitchAPIRequest("https://api.twitch.tv/helix/games/?name=" + name)
            r.raise_for_status()
            try:
                r = r.json()["data"][0]
            except IndexError:
                return await ctx.send(msgs['games']['no_results'])
            e.title = r["name"]
            e.description = f"[{msgs['games']['view_streams']}](https://www.twitch.tv/directory/game/{r['name'].replace(' ', '%20')})"
            e.set_thumbnail(url=r["box_art_url"].format(width=285, height=380))
            r2 = http.Games.IGDBSearchGame(name)
            rjson = r2.json()
            if r2.status_code != 200 or len(rjson) == 0:
                e.add_field(
                    name=msgs['games']['game_details_title'],
                    value=msgs['games']['igdb_fetch_error'].format(error=r2.status_code)
                )
                e.set_footer(text=msgs['games']['game_id'].format(id=r['id']))
            else:
                rjson = rjson[0]
                ratings = round(rjson['rating']/10, 1)
                summary = rjson['summary'][:1000]
                if len(summary) == 1000:
                    summary += f"... {msgs['games']['info_cutoff']}"
                if ratings > 5:
                    rate_emoji = "\\👍"
                else:
                    rate_emoji = "\\👎"
                e.add_field(
                    name=msgs['games']['game_rating']['name'],
                    value=msgs['games']['game_rating']['value'].format(emoji=rate_emoji, score=ratings, count=rjson['rating_count'])
                )
                e.add_field(
                    name=msgs['games']['release_date'],
                    value=time.strftime('%B %d, %Y', time.gmtime(rjson['first_release_date']))
                )
                e.add_field(
                    name=msgs['games']['game_description'],
                    value=summary,
                    inline=False
                )
                e.description += f" • [{msgs['games']['view_on_igdb']}](https://www.igdb.com/games/{rjson['slug']})"
                e.set_footer(text=f"{msgs['games']['game_id'].format(id=r['id'])} • IGDB ID: {rjson['id']}")
            await ctx.send(embed=e)
        except:
            await ctx.send(traceback.format_exc())

    @commands.command(pass_context=True)
    async def top(self, ctx, cnt: int = 10):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        e = discord.Embed(color=discord.Color(0x6441A4), title=msgs['games']['top_games'])
        r = http.TwitchAPIRequest("https://api.twitch.tv/kraken/games/top?limit=10")
        r.raise_for_status()
        r = r.json()["top"]
        place = 1
        for game in r:
            e.add_field(inline=False, name=f"`{place}.` {game['game']['name']}", value=msgs['games']['top_games_desc'].format(view_count=game['viewers'], channel_count=game['channels']))
            place += 1
        await ctx.send(embed=e)

class GameStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = {
            "bronze": "<:ow_bronze:338113846432628736>",
            "silver": "<:ow_silver:338113846734618624>",
            "gold": "<:ow_gold:338113846533292042>",
            "platinum": "<:ow_platinum:338113846550200331>",
            "diamond": "<:ow_diamond:338113846172450818>",
            "master": "<:ow_master:338113846377971719>",
            "grandmaster": "<:ow_grandmaster:338113846503931905>"
        }

    #@commands.group(aliases=['ow'])
    async def overwatch(self, ctx):
        if ctx.invoked_subcommand is None:
            return await ctx.send("insert help here")

    #@overwatch.command(aliases=['qp'])
    async def quickplay(self, ctx, platform, *, username):
        msgs = await lang.get_lang(ctx)
        username = FormatOWAPIUser(username)
        if platform == "pc" and not "-" in username:
            return await ctx.send(msgs['games']['invalid_battletag'])
        if not platform in ["pc", "psn", "xbl"]:
            return await ctx.send(msgs['games']['invalid_platform'])
        async with ctx.channel.typing():
            request = http.Games.OverwatchAPIRequest(f"/u/{username}/stats?platform={platform}")
        re = request.json()
        re = re.get('any') or re.get('us') or re.get('eu') or re.get('kr')
        if request.status_code == 404 or stats is None:
            return await ctx.send(msgs['games']['no_stats_overwatch'])
        elif request.status_code != 200:
            return await ctx.send(f"{msgs['games']['generic_error']} {r.status_code}")
        re = re['stats']['quickplay']
        e = discord.Embed(
            color=0x2196F3,
            title="Overwatch Stats (Quickplay)",
            description=f"{round()}"
        )
        e.set_footer(text=msgs['games']['powered_by_overwatch'])
        e.set_thumbnail(url=re['overall_stats']['avatar'])
        e.set_author(
            name=username.replace('-', '#').replace('_', ' '),
            url=f"https://playoverwatch.com/en-us/career/{platform}/{username}",
            icon_url=re['overall_stats']['avatar']
        )

    @commands.command(aliases=['ow'])
    @commands.cooldown(rate=1, per=2)
    async def overwatch(self, ctx, platform, *, username):
        msgs = await lang.get_lang(ctx)
        username = FormatOWAPIUser(username)
        if platform == "pc" and not "-" in username:
            return await ctx.send(msgs['games']['invalid_battletag'])
        elif not platform in ["pc", "psn", "xbl"]:
            return await ctx.send(msgs['games']['invalid_platform'])
        async with ctx.channel.typing():
            r = http.Games.OverwatchAPIRequest(f"/u/{username}/stats?platform={platform}")
        rjson = r.json()
        stats = rjson.get('any') or rjson.get('us') or rjson.get('eu') or rjson.get('kr')
        if r.status_code == 404 or stats is None:
            return await ctx.send(msgs['games']['no_stats_overwatch'])
        elif r.status_code != 200:
            return await ctx.send(f"{msgs['games']['generic_error']} {r.status_code}")
        stats = stats['stats']['competitive']
        e = discord.Embed(color=0x2196F3, title="Overwatch Stats (Competitive)")
        e.set_footer(text=msgs['games']['powered_by_overwatch'])
        e.set_author(
            name=username.replace('-', '#').replace('_', ' '),
            url=f"https://playoverwatch.com/en-us/career/{platform}/{username}",
            icon_url=stats['overall_stats']['avatar']
        )
        e.set_thumbnail(
            url=stats['overall_stats']['avatar']
        )
        e.description = f"{round(stats['game_stats']['time_played'])} total hours played"
        e.add_field(
            name="Competitive Rank",
            value=f"{self.emoji[stats['overall_stats']['tier']]} {stats['overall_stats']['comprank']}"
        )
        e.add_field(
            name="Level",
            value=str(((stats['overall_stats']['prestige'] or 0)*100) + stats['overall_stats']['level'])
        )
        e.add_field(
            name="Stats",
            value=textwrap.dedent(f"""\
            • {stats['game_stats']['damage_done']} damage dealt
              most in game: {stats['game_stats']['all_damage_done_most_in_game']}
            • {stats['game_stats']['healing_done']} healing given
              most in game: {stats['game_stats']['healing_done_most_in_game']}
            • {stats['game_stats']['offensive_assists']} offensive assists
              most in game: {stats['game_stats']['offensive_assists_most_in_game']}
            • {stats['game_stats']['defensive_assists']} defensive assists
              most in game: {stats['game_stats']['defensive_assists_most_in_game']}
            """)
        )
        e.add_field(
            name="Matches Played",
            value=textwrap.dedent(f"""\
            • {stats['game_stats']['games_played']} total
            • {stats['game_stats']['games_won']} wins ({round(stats['game_stats']['games_won']/stats['game_stats']['games_played']*100)}%)
            • {stats['game_stats']['games_tied']} ties
            • {stats['game_stats']['games_lost']} losses
            • {stats['game_stats']['cards']} end-of-match cards
            """)
        )
        e.add_field(
            name="Kills/Deaths",
            value=textwrap.dedent(f"""\
            • {stats['game_stats']['eliminations']} kills
              most in game: {stats['game_stats']['eliminations_most_in_game']}
              env kills: {stats['game_stats']['environmental_kills']}
            • {stats['game_stats']['deaths']} deaths
            • {stats['game_stats']['kpd']} kills per death
            """)
        )
        e.add_field(
            name="Medals",
            value=textwrap.dedent(f"""\
            • {stats['game_stats']['medals']} total
            • {stats['game_stats']['medals_gold']} gold
            • {stats['game_stats']['medals_silver']} silver
            • {stats['game_stats']['medals_bronze']} bronze
            """)
        )
        await ctx.send(embed=e)

    @commands.command(pass_context=True, aliases=["fn"])
    @commands.cooldown(rate=1, per=2)
    async def fortnite(self, ctx, platform, *, epic_nickname):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        if not platform in ["pc", "psn", "xbl"]:
            await ctx.send(msgs['games']['invalid_platform'])
            return
        r = await http.Games.TRNFortniteRequest(self, "/{}/{}".format(platform, epic_nickname))
        if r.status_code == 404 or r.json().get("error") == "Player Not Found":
            await ctx.send(msgs['games']['no_stats_fortnite'])
            return
        elif r.status_code != 200:
            await ctx.send(f"{msgs['games']['generic_error']} {r.status_code}")
            return
        try:
            stats = r.json()['stats'].get('p2') or r.json()['stats'].get('p10') or r.json()['stats'].get('p9')
        except JSONDecodeError:
            return await ctx.send(msgs['games']['no-stats_fortnite'])
        e = discord.Embed(color=0x2196F3, title="Fortnite Stats")
        e.set_author(name=r.json()['epicUserHandle'] + " on " + r.json()['platformNameLong'])
        e.description = "{} games played".format(stats['matches']['value'])
        e.add_field(name="Score", value="• {} total\n• {} per match".format(stats['score']['value'], stats['scorePerMatch']['value']))
        e.add_field(name="Kill Stats", value="• {} total\n• {} kills per death\n• {} per match".format(stats['kills']['value'], stats['kd']['value'], stats['kpg']['value']))
        e.add_field(name="Standings", value="• {} wins\n• {} times reached top 3\n• {} times reached top 5\n• {} times reached top 10\n• {} times reached top 25".format(stats['top1']['value'], stats['top3']['value'], stats['top5']['value'], stats['top10']['value'], stats['top25']['value']))
        e.add_field(name="Win Percentage", value="{}%".format(round(stats['top1']['valueInt'] / stats['matches']['valueInt'], 2) * 100))
        e.set_footer(text=msgs['games']['powered_by_fortnite'])
        await ctx.send(embed=e)

    @commands.command(pass_context=True)
    @commands.cooldown(rate=1, per=2)
    async def pubg(self, ctx, platform, *, username): # nvm api doesn't work anyways
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        if not platform in ["pc", "psn", "xbl"]:
            await ctx.send(msgs['games']['invalid_platform'])
            return


def setup(bot):
    bot.add_cog(Games(bot))
    bot.add_cog(GameStats(bot))
