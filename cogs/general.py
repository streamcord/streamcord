from discord.ext import commands
import discord
import time
import requests
import sys
from utils.functions import GET_UPTIME
from utils import presence
import psutil

class General:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["commands"])
    async def cmds(self, ctx):
        await ctx.send(embed=presence.send_commands_content())

    @commands.cooldown(rate=1, per=3)
    @commands.command(pass_context=True)
    async def info(self, ctx):
        e = discord.Embed(color=discord.Color(0x6441A4), title="<:twitch:404633403603025921> TwitchBot Stats")
        u = GET_UPTIME(self.bot.uptime)
        e.add_field(name="Uptime", value=u, inline=False)
        e.add_field(name="Usage", value="**•** {} servers\n**•** {} users\n**•** {} commands run\n**•** {} live checks\n**•** {} streamer notifications".format(len(self.bot.guilds), len(list(self.bot.get_all_members())), self.bot.cmds, len(self.bot.livecheck), len(self.bot.notifs)))
        e.add_field(name="Version", value="Python {}\ndiscord.py {}".format(sys.version.split()[0], discord.__version__))
        try:
            e.add_field(name="Shard Info", value="**•** Current shard: {} (real: {})\n**•** Shard latency: {}ms\n**•** Total shards: {}".format(ctx.guild.shard_id + 1, ctx.guild.shard_id, round(self.bot.latency*1000), self.bot.shard_count))
        except:
            e.add_field(name="Shard Info", value="**•** Current shard: {} (real: {})\n**•** Shard latency: {}ms\n**•** Total shards: {}".format("None", "None", round(self.bot.latency*1000), self.bot.shard_count))
        mem = psutil.virtual_memory()
        e.add_field(name="System", value="""
**•** {}% CPU
**•** {}/{}MB memory used
        """.format(psutil.cpu_percent(interval=1), round(mem.used/1000000), round(mem.total/1000000)))
        e.add_field(name="Links", value="""
**•** Website: https://twitchbot.io
**•** Discord: https://discord.gg/UNYzJqV
**•** Upvote: https://discordbots.org/bot/twitch/vote
**•** Donate: https://patreon.com/devakira
        """, inline=False)
        e.add_field(name="Developer", value="Akira#4587", inline=False)
        e.add_field(name="Patrons", value=", ".join(map(lambda m: str(m), filter(lambda m: 460491951729278988 in map(lambda r: r.id, m.roles) and not 424762262775922692 in map(lambda r: r.id, m.roles), self.bot.get_guild(294215057129340938).members))))
        await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=3)
    @commands.command(pass_context=True)
    async def ping(self, ctx):
        t = time.time()
        await ctx.trigger_typing()
        t2 = round((time.time() - t) * 1000)
        await ctx.send("Pong! {}ms".format(t2))

    @commands.command(pass_context=True)
    async def invite(self, ctx):
        await ctx.send("**{}**, you can invite me to a server with this link:\n**<https://discordapp.com/api/oauth2/authorize?client_id=375805687529209857&permissions=8&scope=bot>**".format(ctx.message.author.name))
        await ctx.send("You can also join the support server here:\n**<https://discord.me/konomi>**")

    @commands.cooldown(rate=1, per=3)
    @commands.command(pass_context=True)
    async def status(self, ctx):
        await ctx.trigger_typing()
        e = discord.Embed(color=discord.Color(0x6441A4), title="<:twitch:404633403603025921> Twitch Status")
        r = requests.get("https://cjn0pxg8j9zv.statuspage.io/api/v2/summary.json")
        r.raise_for_status()
        r = r.json()["components"]
        for c in r:
            emote = "<:online:405514304880771072>"
            if c["status"] == "partial_outage":
                emote = "<:away:405514303999967232>"
            elif c["status"] == "major_outage":
                emote = "<:dnd:405514304020807681>"
            e.add_field(name="{} {}".format(emote, c["name"]), value="Current status: `{}`".format(c["status"]))
        await ctx.send(embed=e)

def setup(bot):
    bot.add_cog(General(bot))
