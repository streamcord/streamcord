from discord.ext import commands
import discord
import time
import requests
import aiohttp
import sys
import os
from utils import presence, lang, paginator, settings, functions
from textwrap import dedent
import psutil
import tinydb
import datadog
import logging
import traceback
import rethinkdb as r
r = r.RethinkDB()


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["commands"])
    async def cmds(self, ctx):
        msgs = await lang.get_lang(ctx)
        await ctx.send(embed=lang.EmbedBuilder(msgs['commands_list']))

    @commands.cooldown(rate=1, per=3)
    @commands.command()
    async def info(self, ctx):
        async with ctx.channel.typing():
            msgs = await lang.get_lang(ctx)
            e = discord.Embed(
                color=discord.Color(0x6441A4),
                title=msgs['general']['stats_command']['title']
            )
            uptime = functions.GetBotUptime(self.bot.uptime)
            mem = psutil.virtual_memory()
            e.add_field(
                name=msgs['general']['stats_command']['uptime'],
                value=uptime,
                inline=False
            )
            lr_cnt = r.table('live_role').count().run(self.bot.rethink)
            notif_cnt = r.table('notifications').count().run(self.bot.rethink)
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
                value="Akira#8185 - [Website](https://akira.arraycord.dev)",
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
    @commands.command(pass_context=True)
    async def status(self, ctx):
        async with ctx.channel.typing():
            msgs = await lang.get_lang(ctx)
            e = discord.Embed(
                color=discord.Color(0x6441A4),
                title=msgs['general']['status']['title']
            )
            r = requests.get(
                "https://cjn0pxg8j9zv.statuspage.io/api/v2/summary.json"
            )
            r.raise_for_status()
            r = r.json()["components"]
            for c in r:
                emote = lang._emoji.cmd_success
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
    async def lang(self, ctx, language=None):
        msgs = await lang.get_lang(ctx)
        if language is None:
            return await ctx.send(
                msgs['general']['lang_current'].format(lang=msgs['_lang_name'])
            )
        else:
            if language == "help":
                lang_help = await lang.gen_lang_help(ctx)
                e = paginator.EmbedPaginator(lang_help, per_page=7)
                return await e.page(ctx)
            if language not in self.bot.languages:
                return await ctx.send(msgs['general']['lang_unavailable'])
            cursor = r.table('user_options').insert(
                {"id": str(ctx.author.id), "lang": language},
                conflict="update"
            ).run(self.bot.rethink, durability="soft", noreply=True)
            msgs = await lang.get_lang(ctx)
            return await ctx.send(
                msgs['general']['lang_set'].format(lang=msgs['_lang_name'])
            )


def setup(bot):
    bot.add_cog(General(bot))

    @bot.event
    async def on_message(ctx):
        try:
            if ctx.author.bot:
                return
            elif ctx.content.lower().startswith(tuple(bot.command_prefix)):
                if ctx.author.id in settings.BannedUsers:
                    return await ctx.channel.send(
                        "You have been banned from using TwitchBot."
                    )
                if not bot.is_ready():
                    msgs = await lang.get_lang(
                        lang.FakeCtxObject(bot, ctx.author)
                    )
                    return await ctx.channel.send(
                        msgs['errors']['not_started']
                    )
                if ctx.guild:
                    logging.info(f"{ctx.author.id} in {ctx.guild.id}: {ctx.clean_content}")
                else:
                    logging.info(f"{ctx.author.id} in DM: {ctx.clean_content}")
                help_cmd = tuple(map(lambda t: t + "help", bot.command_prefix))
                if ctx.content.lower() in help_cmd:
                    # send help command
                    msgs = await lang.get_lang(
                        lang.FakeCtxObject(bot, ctx.author)
                    )
                    if not settings.UseBetaBot:
                        datadog.statsd.increment(
                            'bot.commands_run',
                            tags=["command:help"]
                        )
                    return await ctx.channel.send(
                        embed=lang.EmbedBuilder(msgs['help_command'])
                    )
                else:
                    splitter = ctx.content.split(' && ')
                    for s in splitter:
                        ctx.content = s
                        await bot.process_commands(ctx)
            elif ctx.guild is None:
                return
        except Exception:
            await ctx.channel.send(
                f"An unexpected error occurred:\n{traceback.format_exc()}"
            )
