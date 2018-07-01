from discord.ext import commands
import discord
import time
import requests
import sys
from utils.functions import GET_UPTIME
from utils import presence

class General:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["commands"])
    async def cmds(self, ctx):
        await ctx.send(embed=presence.send_commands_content())

    @commands.command(pass_context=True)
    async def info(self, ctx):
        await ctx.trigger_typing()
        e = discord.Embed(color=discord.Color(0x6441A4), title="<:twitch:404633403603025921> TwitchBot Stats")
        u = GET_UPTIME(self.bot.uptime)
        e.add_field(name="Uptime", value=u, inline=False)
        e.add_field(name="Version", value="Python {}\ndiscord.py {}".format(sys.version.split()[0], discord.__version__))
        e.add_field(name="Usage", value="**•** {} servers\n**•** {} users\n**•** {} commands run\n**•** {} live checks\n**•** {} streamer notifications".format(len(self.bot.guilds), len(list(self.bot.get_all_members())), self.bot.cmds, len(self.bot.livecheck), len(self.bot.notifs)), inline=False)
        e.add_field(name="Shard Info", value="**•** Current shard: {} (real: {})\n**•** Shard latency: {}ms\n**•** Total shards: {}".format(ctx.guild.shard_id + 1, ctx.guild.shard_id, round(self.bot.latency*1000), self.bot.shard_count))
        e.add_field(name="Website", value="https://twitch.disgd.pw", inline=False)
        e.add_field(name="Discord", value="https://discord.me/konomi", inline=False)
        e.add_field(name="Upvote", value="https://discordbots.org/bot/twitch/vote", inline=False)
        e.add_field(name="Donate", value="https://paypal.me/akireee", inline=False)
        e.add_field(name="Developer", value="Akira#4587 • [Website](https://disgd.pw)", inline=False)
        e.set_thumbnail(url=self.bot.user.avatar_url)
        await ctx.send(embed=e)

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
