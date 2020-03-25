import time
import sys
from os import getenv
from textwrap import dedent
import logging
import traceback

import discord
from discord.ext import commands
import psutil
import requests
from rethinkdb import RethinkDB
from ..utils import lang, paginator, functions
r = RethinkDB()


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["commands"])
    async def cmds(self, ctx):
        msgs = await lang.get_lang(ctx)
        e = lang.EmbedBuilder(msgs['commands_list'])
        if getenv('ENABLE_PRO_FEATURES') == '1':
            e.title = "<:twitch:404633403603025921> Streamcord Pro Commands"
            e.add_field(
                name="Moderation",
                value="`?twitch ban <user> [reason]`\n`?twitch kick <user> [reason]`\n`?twitch purge <n>` - Deletes the last n messages",
                inline=False)
        await ctx.send(embed=e)

    @commands.cooldown(rate=1, per=3)
    @commands.command()
    async def info(self, ctx):
        async with ctx.channel.typing():
            msgs = await lang.get_lang(ctx)
            e = discord.Embed(
                color=discord.Color(0x6441A4),
                title=msgs['general']['stats_command']['title']
            )
            uptime = functions.get_bot_uptime(self.bot.uptime)
            mem = psutil.virtual_memory()
            e.add_field(
                name=msgs['general']['stats_command']['uptime'],
                value=uptime,
                inline=False
            )
            lr_cnt = await r.table('live_role').count().run(self.bot.rethink)
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
    @commands.command(pass_context=True)
    async def status(self, ctx):
        async with ctx.channel.typing():
            msgs = await lang.get_lang(ctx)
            e = discord.Embed(
                color=discord.Color(0x6441A4),
                title=msgs['general']['status']['title']
            )
            re = requests.get(
                "https://cjn0pxg8j9zv.statuspage.io/api/v2/summary.json"
            )
            re.raise_for_status()
            re = re.json()["components"]
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
    async def lang(self, ctx, language=None):
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
        await r.table('user_options') \
            .insert(
                {"id": str(ctx.author.id), "lang": language},
                conflict="update"
            ) \
            .run(self.bot.rethink, durability="soft", noreply=True)
        msgs = await lang.get_lang(ctx, force=language)
        return await ctx.send(
            msgs['general']['lang_set'].format(lang=msgs['_lang_name']))


def setup(bot):
    bot.add_cog(General(bot))

    @bot.event
    async def on_message(ctx):
        try:
            if ctx.author.bot:
                return
            if ctx.content.lower().startswith(tuple(bot.command_prefix)):
                if str(ctx.author.id) in getenv('BANNED_USERS').split(','):
                    return await ctx.channel.send(
                        "You have been banned from using Streamcord.")
                if not bot.is_ready():
                    msgs = await lang.get_lang(
                        lang.FakeCtxObject(bot, ctx.author))
                    return await ctx.channel.send(msgs['errors']['not_started'])
                if ctx.guild:
                    logging.info('%i in %i: %s', ctx.author.id, ctx.guild.id, ctx.clean_content)
                else:
                    logging.info('%i in DM: %s', ctx.author.id, ctx.clean_content)
                help_cmd = tuple(map(lambda t: t + "help", bot.command_prefix))
                if ctx.content.lower() in help_cmd:
                    await ctx.channel.trigger_typing()
                    # send help command
                    msgs = await lang.get_lang(
                        lang.FakeCtxObject(bot, ctx.author))
                    await functions.dogstatsd.increment('bot.commands_run', tags=['command:help'])
                    e = lang.EmbedBuilder(msgs['help_command'])
                    if getenv('ENABLE_PRO_FEATURES') == '1':
                        e.title = "<:twitch:404633403603025921> **Streamcord Pro Help**"
                        e.set_field_at(
                            0,
                            name="Commands",
                            value="Streamcord responds to commands starting with `?twitch`. Type `?twitch commands` to view all runnable commands.")
                        e.remove_field(4)
                        e.remove_field(5)
                        e.insert_field_at(
                            0,
                            name="Pro Bot",
                            value="This server is running a special instance of Streamcord only available to Patrons and partners. [Learn More](https://streamcord.io/twitch/pro)",
                            inline=False)
                    return await ctx.channel.send(embed=e)
                splitter = ctx.content.split(' && ')
                for s in splitter:
                    ctx.content = s
                    await bot.process_commands(ctx)
            elif ctx.guild is None:
                return
        except Exception:
            msgs = await lang.get_lang(lang.FakeCtxObject(bot, ctx.author))
            await ctx.channel.send(f"{msgs['games']['generic_error']}\n{traceback.format_exc()}")
