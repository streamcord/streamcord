import discord
import logging

from discord.ext import commands
from time import time
from typing import Union
from . import emoji


class FakeCtxObject:
    def __init__(self, bot, user):
        self.bot = bot
        self.author = user


async def get_lang(ctx: Union[commands.Context, FakeCtxObject], force=None) -> dict:
    if force is not None:
        return ctx.bot.languages[force]
    ctime = time()
    user = await ctx.bot.mongo.dashboard.userPreferences.find_one(
        {'_id': str(ctx.author.id)},
        projection={'lang': 1})
    ctime = round((time() - ctime) * 1000)
    logging.info('Fetched language preferences for %i in %ims (%s)',
                 ctx.author.id, ctime, (user or {}).get('lang', 'en'))
    if user is None:
        return ctx.bot.languages['en']
    return ctx.bot.languages[user.get('lang', 'en')]


async def gen_lang_help(ctx: commands.Context) -> discord.Embed:
    msgs = await get_lang(ctx)
    e = discord.Embed(
        color=0x9146ff,
        title=msgs['general']['available_translations']['title'])
    e.set_footer(text=msgs['general']['available_translations']['footer'])
    for k, v in ctx.bot.languages.items():
        indicator = ""
        if msgs['_lang_name'] == v['_lang_name']:
            indicator = emoji.left_arrow
        e.add_field(
            name=f"{v['_lang_emoji']} {v['_lang_name']} {indicator}",
            value=f"`!twitch lang {k}` to set\nTranslated by {v['_translator']}",
            inline=False)
    return e


def build_embed(embed: dict) -> discord.Embed:
    e = discord.Embed(color=0x9146ff)
    if embed.get('title') is not None:
        e.title = embed['title']
    if embed.get('description') is not None:
        e.description = embed['description']
    if embed.get('footer') is not None:
        e.set_footer(text=embed['footer'])
    for field in embed.get('fields', []):
        e.add_field(
            name=field.get('name', False) or field.get('title', False),
            value=field['value'],
            inline=field.get('inline', True))
    return e
