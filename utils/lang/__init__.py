import discord
import asyncio
import logging
import os, json
import requests
import shutil
import json
from zipfile import ZipFile
from .. import settings
from . import _emoji
import rethinkdb as r
r = r.RethinkDB()

def load_langs(bot):
    bot.languages = {}
    lang_dir = os.path.join(os.getcwd(), 'utils', 'lang', 'i18n')
    logging.info("Building translations...")
    r = requests.get(f"https://api.crowdin.com/api/project/twitchbot/export?key={settings.Crowdin}")
    if r.status_code != 200:
        logging.warn(f'Failed to build translations from Crowdin:\n{r.text}')
    logging.info("Downloading ZIP...")
    r = requests.get(f"https://api.crowdin.com/api/project/twitchbot/download/all.zip?key={settings.Crowdin}", stream=True)
    with open(os.path.join(os.getcwd(), 'utils', 'lang', 'i18n.zip'), 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    logging.info("Clearing old translations...")
    for file in os.listdir(lang_dir):
        fpath = os.path.join(lang_dir, file)
        try:
            if os.path.isfile(fpath):
                os.unlink(fpath)
            elif os.path.isdir(fpath):
                shutil.rmtree(fpath)
        except Exception as e:
            logging.error(e)
    logging.info("Extracting translations ZIP...")
    with ZipFile(os.path.join(os.getcwd(), 'utils', 'lang', 'i18n.zip'), 'r') as zip:
        zip.extractall(lang_dir)
    logging.info("Importing translations...")
    for file in os.listdir(lang_dir):
        fpath = os.path.join(lang_dir, file)
        if os.path.isdir(fpath):
            logging.debug(f"Loading {file}")
            f = open(os.path.join(lang_dir, file, 'main.json'), 'r', encoding="utf-8")
            content = json.loads(f.read())
            f.close()
            bot.languages[file] = content
    os.unlink(os.path.join(os.getcwd(), 'utils', 'lang', 'i18n.zip'))
    logging.info(f"Loaded {len(bot.languages)} languages")

async def get_lang(ctx):
    user = r.table('user_options').get(str(ctx.author.id)).run(ctx.bot.rethink, durability="soft")
    if user is None:
        return ctx.bot.languages['en']
    return ctx.bot.languages[user.get('lang', 'en')]

async def gen_lang_help(ctx):
    msgs = await get_lang(ctx)
    e = discord.Embed(color=discord.Color(0x6441A4), title=msgs['general']['available_translations']['title'])
    e.set_footer(text=msgs['general']['available_translations']['footer'])
    for k, v in ctx.bot.languages.items():
        indicator = ""
        if msgs['_lang_name'] == v['_lang_name']:
            indicator = _emoji.left_arrow
        e.add_field(name=f"{v['_lang_emoji']} {v['_lang_name']} {indicator}", value=f"`!twitch lang {k}` to set\nTranslated by {v['_translator']}", inline=False)
    return e

def EmbedBuilder(embed):
    e = discord.Embed(color=discord.Color(0x6441A4))
    if embed.get('title') is not None:
        e.title = embed['title']
    if embed.get('description') is not None:
        e.description = embed['description']
    if embed.get('footer') is not None:
        e.set_footer(text=embed['footer'])
    for field in embed.get('fields', []):
        e.add_field(name=field.get('name', False) or field.get('title', False), value=field['value'], inline=field.get('inline', True))
    return e

class FakeCtxObject:
    def __init__(self, bot, user):
        self.bot = bot
        self.author = user
