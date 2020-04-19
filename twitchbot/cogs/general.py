import discord
import psutil
import sys
import time

from discord.ext import commands
from os import getenv
from rethinkdb import RethinkDB
from textwrap import dedent
from ..utils import lang, paginator, functions
from .. import TwitchBot

r = RethinkDB()
r.set_loop_type('asyncio')


class General(commands.Cog):
    def __init__(self, bot):
        self.bot: TwitchBot = bot

    @commands.command(aliases=["commands"])
    async def cmds(self, ctx):
        msgs = await lang.get_lang(ctx)
        e = lang.build_embed(msgs['commands_list'])
        if getenv('ENABLE_PRO_FEATURES') == '1':
            e.title = lang.emoji.twitch_icon + "Streamcord Pro Commands"
            e.set_field_at(
                4,
                name="Live Role",
                value="`?twitch lr view` - View the current live role config\n"
                      "`?twitch lr check` - Debug the current live role config\n"
                      "`?twitch lr set role` - Set the live role and force update member roles\n"
                      "`?twitch lr set filter` - Set the filter role\n"
                      "`?twitch lr delete` - Delete the live role config\n"
                      "`?twitch lr delete filter` - Delete the filter role config",
                inline=False)
            e.add_field(
                name="Moderation",
                value="`?twitch ban <user> [reason]`\n`?twitch kick <user> [reason]`\n`?twitch purge <n>` - Deletes "
                      "the last n messages",
                inline=False)
        await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=3)
    @commands.command()
    async def info(self, ctx):
        async with ctx.channel.typing():
            msgs = await lang.get_lang(ctx)
            e = discord.Embed(
                color=discord.Color(0x9146ff),
                title=msgs['general']['stats_command']['title']
            )
            uptime = functions.get_bot_uptime(self.bot.uptime)
            mem = psutil.virtual_memory()
            e.add_field(
                name=msgs['general']['stats_command']['uptime'],
                value=uptime,
                inline=False
            )
            lr_cnt = 0
            notif_cnt = await r.table('notifications').count().run(self.bot.rethink)
            e.add_field(
                name=msgs['general']['stats_command']['usage'],
                value=dedent(f"""\
                    **·** {lr_cnt} live roles
                    **·** {notif_cnt} stream notifications
                    """)
            )
            e.add_field(
                name=msgs['general']['stats_command']['version'],
                value=dedent(f"""\
                    **·** Version {getenv('VERSION')}
                    **·** Python {sys.version.split(' ')[0]}
                    **·** discord.py {discord.__version__}
                    """)
            )
            if ctx.guild is None:
                e.add_field(
                    name=msgs['general']['stats_command']['shard_info'],
                    value=dedent(f"""\
                        **·** Shard latency: {round(self.bot.latency*1000)}ms
                        **·** Total shards: {self.bot.shard_count}
                        """)
                )
            else:
                e.add_field(
                    name=msgs['general']['stats_command']['shard_info'],
                    value=dedent(f"""\
                        **·** {len(self.bot.guilds)} servers
                        **·** {len(self.bot.users)} members
                        **·** Current shard: {ctx.guild.shard_id}
                        **·** Shard latency: {round(self.bot.latency*1000)}ms
                        **·** Total shards: {self.bot.shard_count}
                        """)
                )
            e.add_field(
                name=msgs['general']['stats_command']['system'],
                value=dedent(f"""\
                    **·** {psutil.cpu_percent(interval=1)}% CPU
                    **·** {round(mem.used/1000000)}/{round(mem.total/1000000)}MB RAM
                    """)
            )
            e.add_field(
                name=msgs['general']['stats_command']['links']['title'],
                value=msgs['general']['stats_command']['links']['value'],
                inline=False
            )
            e.add_field(
                name=msgs['general']['stats_command']['developer'],
                value="Akira#8185",
                inline=False
            )
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
        msgs = await lang.get_lang(ctx)
        await ctx.send(
            msgs['general']['invite_message_1'].format(user=ctx.author.name)
        )
        await ctx.send(msgs['general']['invite_message_2'])

    @commands.cooldown(rate=1, per=3)
    @commands.command()
    async def status(self, ctx):
        async with ctx.channel.typing():
            msgs = await lang.get_lang(ctx)
            e = discord.Embed(
                color=discord.Color(0x9146ff),
                title=msgs['general']['status']['title']
            )
            re = await self.bot.chttp.get_twitch_api_status()
            for c in re:
                emote = lang.emoji.cmd_success
                if c["status"] in ["partial_outage", "major_outage"]:
                    emote = lang.emoji.cmd_fail
                e.add_field(
                    name="{}{}".format(emote, c["name"]),
                    value=msgs['general']['status']['current_status'].format(
                        status=c['status']
                    ),
                    inline=False
                )
        await ctx.send(embed=e)

    @commands.command(aliases=["language"])
    async def lang(self, ctx: commands.Context, language: str = None):
        msgs = await lang.get_lang(ctx)
        if language is None:
            return await ctx.send(
                msgs['general']['lang_current'].format(lang=msgs['_lang_name'])
            )
        if language == "help":
            lang_help = await lang.gen_lang_help(ctx)
            e = paginator.EmbedPaginator(lang_help, per_page=7)
            return await e.page(ctx)
        if language not in self.bot.languages:
            return await ctx.send(msgs['general']['lang_unavailable'])
        await self.bot.mongo.dashboard.userPreferences.find_one_and_update(
            {'_id': str(ctx.author.id)},
            {'$set': {'lang': language}},
            projection={'_id': 1},
            upsert=True)
        msgs = await lang.get_lang(ctx, force=language)
        return await ctx.send(
            msgs['general']['lang_set'].format(lang=msgs['_lang_name']))


def setup(bot: TwitchBot):
    bot.add_cog(General(bot))
