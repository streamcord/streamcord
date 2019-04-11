from discord.ext import commands
import discord
import time
import requests, aiohttp
import sys, os
from utils import presence, lang, paginator, settings, functions
from textwrap import dedent
import psutil
import tinydb
import datadog
import logging, traceback
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
            e = discord.Embed(color=discord.Color(0x6441A4), title=msgs['general']['stats_command']['title'])
            uptime = functions.GetBotUptime(self.bot.uptime)
            mem = psutil.virtual_memory()
            e.add_field(name=msgs['general']['stats_command']['uptime'], value=uptime, inline=False)
            e.add_field(name=msgs['general']['stats_command']['usage'], value=dedent(f"""\
            **·** {len(self.bot.guilds)} servers
            **·** {len(list(self.bot.get_all_members()))} members
            **·** {r.table('live_role').count().run(self.bot.rethink, durability="soft")} live roles
            **·** {r.table('notifications').count().run(self.bot.rethink, durability="soft")} stream notifications
            """))
            e.add_field(name=msgs['general']['stats_command']['version'], value=dedent(f"""\
            **·** Python {sys.version.split(' ')[0]}
            **·** discord.py {discord.__version__}
            """))
            if ctx.guild is None:
                e.add_field(name=msgs['general']['stats_command']['shard_info'], value=dedent(f"""\
                **·** Shard latency: {round(self.bot.latency*1000)}ms
                **·** Total shards: {self.bot.shard_count}
                """))
            else:
                e.add_field(name=msgs['general']['stats_command']['shard_info'], value=dedent(f"""\
                **·** Current shard: {ctx.guild.shard_id}
                **·** Shard latency: {round(self.bot.latency*1000)}ms
                **·** Total shards: {self.bot.shard_count}
                """))
            e.add_field(name=msgs['general']['stats_command']['system'], value=dedent(f"""\
            **·** {psutil.cpu_percent(interval=1)}% CPU
            **·** {round(mem.used/1000000)}/{round(mem.total/1000000)}MB RAM used
            """))
            e.add_field(name=msgs['general']['stats_command']['links']['title'], value=msgs['general']['stats_command']['links']['value'], inline=False)
            e.add_field(name=msgs['general']['stats_command']['developer'], value="Akira#0007", inline=False)
            try:
                e.add_field(name=msgs['general']['stats_command']['patrons'], value=", ".join(map(lambda m: str(m), filter(lambda m: 444294762783178752 in map(lambda r: r.id, m.roles) and not 424762262775922692 in map(lambda r: r.id, m.roles), self.bot.get_guild(294215057129340938).members))))
            except:
                pass
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
        await ctx.send(msgs['general']['invite_message_1'].format(user=ctx.message.author.name))
        await ctx.send(msgs['general']['invite_message_2'])

    @commands.cooldown(rate=1, per=3)
    @commands.command(pass_context=True)
    async def status(self, ctx):
        async with ctx.channel.typing():
            msgs = await lang.get_lang(ctx)
            e = discord.Embed(color=discord.Color(0x6441A4), title=msgs['general']['status']['title'])
            r = requests.get("https://cjn0pxg8j9zv.statuspage.io/api/v2/summary.json")
            r.raise_for_status()
            r = r.json()["components"]
            for c in r:
                emote = lang._emoji.cmd_success
                if c["status"] in ["partial_outage", "major_outage"]:
                    emote = lang.emoji.cmd_fail
                e.add_field(name="{}{}".format(emote, c["name"]), value=msgs['general']['status']['current_status'].format(status=c['status']), inline=False)
        await ctx.send(embed=e)

    @commands.command(aliases=["language"])
    async def lang(self, ctx, language = None):
        msgs = await lang.get_lang(ctx)
        if language is None:
            return await ctx.send(msgs['general']['lang_current'].format(lang=msgs['_lang_name']))
        else:
            if language == "help":
                lang_help = await lang.gen_lang_help(ctx)
                e = paginator.EmbedPaginator(lang_help, per_page=7)
                return await e.page(ctx)
            if not language in self.bot.languages:
                return await ctx.send(msgs['general']['lang_unavailable'])
            cursor = r.table('user_options').insert({"id": str(ctx.author.id), "lang": language}, conflict="update").run(self.bot.rethink, durability="soft", noreply=True)
            msgs = await lang.get_lang(ctx)
            return await ctx.send(msgs['general']['lang_set'].format(lang=msgs['_lang_name']))


def setup(bot):
    bot.add_cog(General(bot))

    @bot.event
    async def on_message(message):
        try:
            datadog.statsd.increment('bot.messages_received')
            if message.author.bot:
                return
            elif message.content.lower().startswith(tuple(bot.command_prefix)):
                if message.author.id in settings.BannedUsers:
                    return await message.channel.send("You have been banned from using TwitchBot.")
                if not bot.is_ready():
                    msgs = await lang.get_lang(lang.FakeCtxObject(bot, message.author))
                    return await message.channel.send(msgs['errors']['not_started'])
                if message.guild:
                    logging.info("{0.author} {0.author.id} in {0.guild.name} {0.guild.id}: {0.clean_content}".format(message))
                else:
                    logging.info("{0.author} {0.author.id} in DM: {0.clean_content}".format(message))
                if message.content.lower() in tuple(map(lambda t: t + "help", bot.command_prefix)):
                    # === Send help command === #
                    msgs = await lang.get_lang(lang.FakeCtxObject(bot, message.author))
                    if not settings.UseBetaBot:
                        datadog.statsd.increment('bot.commands_run', tags=["command:help"])
                    return await message.channel.send(embed=lang.EmbedBuilder(msgs['help_command']))
                else:
                    splitter = message.content.split(' && ')
                    for s in splitter:
                        message.content = s
                        await bot.process_commands(message)
            elif message.guild is None:
                return
        except:
            await message.channel.send("An unexpected error occurred:\n" + traceback.format_exc())
