# TODO: Move all event listeners to this file

import discord
import logging
import traceback

from discord.ext import commands
from os import getenv
from rethinkdb import RethinkDB
from ..utils import lang, presence
from ..utils import functions as func
from .. import TwitchBot


class Events(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot: TwitchBot = bot
        self.r = RethinkDB()
        self.r.set_loop_type('asyncio')
        self.log = logging.getLogger('bot.events')
        self.help_triggers = tuple(pre + 'help' for pre in bot.command_prefix)

    async def handle_help(self, message: discord.Message):
        await func.dogstatsd.increment('bot.commands_run', tags=['command:help'])

        l10n = await lang.get_lang(lang.FakeCtxObject(self.bot, message.author))
        e = lang.build_embed(l10n['help_command'])
        if getenv('ENABLE_PRO_FEATURES') == '1':
            # change certain fields to match pro bot
            e.title = lang.emoji.twitch_icon + 'Streamcord Pro Help'
            e.set_field_at(
                0,
                name='Commands',
                value='Streamcord responds to commands starting with `?twitch`. Type `?twitch commands` to view all '
                      'runnable commands.',
                inline=False)
            e.insert_field_at(
                0,
                name='Pro bot',
                value='This server is running a special version of Streamcord that is only available to Patrons and '
                      'partners. [Learn More](https://streamcord.io/twitch/pro)',
                inline=False)

        return await message.channel.send(embed=e)

    async def handle_prefix(self, message: discord.Message):
        if message.guild:
            logging.info('[message event] u=%s, g=%s : %s', message.author.id, message.guild.id, message.clean_content)
        else:
            logging.info('[message event] u=%s, g=None : %s', message.author.id, message.clean_content)

        if message.content.lower() in self.help_triggers:
            return await self.handle_help(message)
        splitter = message.content.split(' && ')
        for cmd in splitter:
            message.content = cmd
            await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content.lower().startswith(tuple(self.bot.command_prefix)):
            try:
                if getenv('ENABLE_PRO_FEATURES') == '1':
                    if message.guild is None:
                        return await message.channel.send('Streamcord Pro can\'t be used in DM.')
                    whitelist = await self.r \
                        .db('TwitchBotPremium')\
                        .table('whitelist')\
                        .get(str(message.guild.id))\
                        .run(self.bot.rethink)
                    if whitelist is None:
                        return await message.channel.send('This server is not whitelisted. Visit '
                                                          f'<https://dash.streamcord.io/servers/{message.guild.id}> '
                                                          'and enable Pro mode to fix this.')

                return await self.handle_prefix(message)
            except Exception:
                logging.exception('on_message event error')
                e = discord.Embed(
                    color=0xf04747,
                    title='An error occurred',
                    description=f'```\n{traceback.format_exc()}\n```')
                await message.channel.send(embed=e)


class ProductionEvents(commands.Cog):
    """
    Events that should only be called in production environments.
    """

    def __init__(self, bot: TwitchBot):
        self.bot = bot
        self.log = logging.getLogger('bot.events')

    @commands.Cog.listener()
    async def on_connect(self):
        await presence.post_connect_event(self.bot.cluster_index)

    @commands.Cog.listener()
    async def on_disconnect(self):
        await presence.post_disconnect_event(self.bot.cluster_index)

    @commands.Cog.listener()
    async def on_ready(self):
        await presence.post_ready_event(self.bot.cluster_index)

    @commands.Cog.listener()
    async def on_shard_ready(self, shard_id: int):
        await presence.post_shard_ready_event(shard_id)


def setup(bot: TwitchBot):
    bot.add_cog(Events(bot))
    if not (func.is_canary_bot() or getenv('ENABLE_PRO_FEATURES') == '1'):
        bot.add_cog(ProductionEvents(bot))
