from discord.ext import commands
import discord, asyncio
from utils.functions import OWAPI_REQUEST, TRN_FORTNITE_REQUEST, RLS_REQUEST
import traceback

class GameStats:
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

    @commands.command(pass_context=True, aliases=["ow"])
    @commands.cooldown(rate=1, per=2)
    async def overwatch(self, ctx, platform, *, username):
        await self.bot.send_typing(ctx.message.channel)
        username = username.replace('#', '-').replace(' ', '_')
        if platform == "pc":
            if not '-' in username:
                await self.bot.say("Please enter your battletag in a format of `name#id`.")
                return
        elif not platform in ["pc", "psn", "xbl"]:
            await self.bot.say("Platform must be one of `pc`, `psn`, or `xbl`.")
        else:
            r = OWAPI_REQUEST("/u/{}/stats?platform={}".format(username, platform))
            if r.status_code == 404 or (r.json().get('any') is None and r.json().get('us') is None and r.json().get('eu') is None and r.json().get('kr') is None):
                await self.bot.say("Player could not be found or no competitive stats exist for this season.")
                return
            elif r.status_code != 200:
                await self.bot.say("An error occurred: {0.status_code}".format(r))
                return
            res = r.json()['any'] or r.json()['us'] or r.json()['eu'] or r.json()['kr']
            stats = {'overall': res['stats']['competitive']['overall_stats'], 'game': res['stats']['competitive']['game_stats']}
            e = discord.Embed(color=0x2196F3, title="Overwatch Stats (Competitive)")
            e.set_author(name=username.replace("-", "#").replace('_', ' '), icon_url=stats['overall']['avatar'], url="https://playoverwatch.com/en-us/career/{}/{}".format(platform, username))
            e.set_thumbnail(url=stats['overall']['avatar'])
            e.description = "{} hours played in {} games".format(stats['game']['time_played'], round(stats['game']['games_played']))
            e.add_field(name="Competitive Rank", value="{} {}".format(self.emoji[stats['overall']['tier']], stats['overall']['comprank']))
            e.add_field(name="Level", value=str((stats['overall']['prestige'] * 100) + stats['overall']['level']))
            e.add_field(name="General", value="• {healing_done} healing done\n• {cards} cards\n• best multikill: {multikill_best} players\n• {damage_done} damage inflicted\n• {environmental_kills} environmental kills".format(**stats['game']))
            e.add_field(name="Matches Played", value="• {total} total\n• {win} wins\n• {loss} losses\n• {wr}% win rate".format(total=stats['overall']['games'], win=stats['overall']['wins'], loss=stats['overall']['losses'], wr=stats['overall']['win_rate']))
            e.add_field(name="Kills/Deaths", value="• {kd} kills per death\n• {el} kills\n• {de} deaths".format(kd=stats['game']['kpd'], el=round(stats['game']['eliminations']), de=round(stats['game']['deaths'])))
            e.add_field(name="Medals", value="• {medals_gold} gold\n• {medals_silver} silver\n• {medals_bronze} bronze".format(**stats['game']))
            e.set_footer(text="Powered by owapi.net")
            await self.bot.say(embed=e)

    @commands.command(pass_context=True, aliases=["fn"])
    @commands.cooldown(rate=1, per=2)
    async def fortnite(self, ctx, platform, *, epic_nickname):
        await self.bot.send_typing(ctx.message.channel)
        if not platform in ["pc", "psn", "xbl"]:
            await self.bot.say("Platform must be one of `pc`, `psn`, or `xbl`.")
            return
        r = await TRN_FORTNITE_REQUEST(self, "/{}/{}".format(platform, epic_nickname))
        if r.status_code == 404 or r.json().get("error") == "Player Not Found":
            await self.bot.say("Player not found. Check the spelling of the username or try a different platform.")
            return
        elif r.status_code != 200:
            await self.bot.say("An error occurred" + str(r.status_code))
            return
        stats = r.json()['stats']['p2'] or r.json()['stats']['p10'] or r.json()['stats']['p9']
        e = discord.Embed(color=0x2196F3, title="Fortnite Stats")
        e.set_author(name=r.json()['epicUserHandle'] + " on " + r.json()['platformNameLong'])
        e.description = "{} games played".format(stats['matches']['value'])
        e.add_field(name="Score", value="• {} total\n• {} per match".format(stats['score']['value'], stats['scorePerMatch']['value']))
        e.add_field(name="Kill Stats", value="• {} total\n• {} kills per death\n• {} per match".format(stats['kills']['value'], stats['kd']['value'], stats['kpg']['value']))
        e.add_field(name="Standings", value="• {} wins\n• {} times reached top 3\n• {} times reached top 5\n• {} times reached top 10\n• {} times reached top 25".format(stats['top1']['value'], stats['top3']['value'], stats['top5']['value'], stats['top10']['value'], stats['top25']['value']))
        e.add_field(name="Win Percentage", value="{}%".format(round(stats['top1']['valueInt'] / stats['matches']['valueInt'], 2) * 100))
        e.set_footer(text='Powered by fortnitetracker.com')
        await self.bot.say(embed=e)

    @commands.command(pass_context=True, aliases=["rl"])
    @commands.cooldown(rate=1, per=2)
    async def rocketleague(self, ctx, platform, *, username):
        await self.bot.send_typing(ctx.message.channel)
        if not platform in ["pc", "psn", "xbl"]:
            await self.bot.say("Platform must be one of `pc`, `psn`, or `xbl`.")
            return
        elif platform == "pc":
            platform = 1
        elif platform == "psn":
            platform = 2
        elif platform == "xbl":
            platform = 3
        r = await RLS_REQUEST(self, "/player?unique_id={}&platform_id={}".format(username, platform))
        if r.status_code == 404:
            await self.bot.say("Player not found. Please enter the username or Steam profile link of the player, and choose the correct platform.")
            return
        elif r.status_code != 200:
            await self.bot.say("An error occurred: {}".format(r.status_code))
            return
        res = r.json()
        e = discord.Embed(color=0x2196F3, title="Rocket League Stats")
        e.set_author(name=res['displayName'] + " on " + res['platform']['name'], url=res['profileUrl'], icon_url=res['avatar'])
        e.add_field(name="Stats", value="• {wins} wins\n• {goals} goals\n• {assists} assists\n• {saves} saves\n• {shots} shots taken\n• {mvps} times MVP".format(**res['stats']))
        e.set_thumbnail(url=res['avatar'])
        e.set_image(url=res['signatureUrl'])
        e.set_footer(text="Powered by rocketleaguestats.com")
        await self.bot.say(embed=e)

    @commands.command(pass_context=True)
    @commands.cooldown(rate=1, per=2)
    async def pubg(self, ctx, platform, *, username): # nvm api doesn't work anyways
        await self.bot.send_typing(ctx.message.channel)
        if not platform in ["pc", "psn", "xbl"]:
            await self.bot.say("Platform must be one of `pc`, `psn`, or `xbl`.")
            return

def setup(bot):
    bot.add_cog(GameStats(bot))
