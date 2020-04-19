import json
import logging
import os
import sys
import shutil
from os import getenv
from zipfile import ZipFile

import aiohttp
import aiofiles
import aiofiles.os


def extract_zip(path, zdir):
    with ZipFile(path, 'r') as zipf:
        zipf.extractall(zdir)


extract_zip = aiofiles.os.wrap(extract_zip)
rmtree = aiofiles.os.wrap(shutil.rmtree)
unlink = aiofiles.os.wrap(os.unlink)


def replace_prefixes(dic):
    for k, v in dic.items():
        if isinstance(v, dict):
            v = replace_prefixes(v)
        elif isinstance(v, list):
            index = 0
            new_v = list(v)
            for i in v:
                new_v[index] = replace_prefixes(i)
                index += 1
            v = new_v
        elif isinstance(v, str):
            v = v.replace('!twitch', '?twitch')
        dic[k] = v
    return dic


async def pull_languages(*, session: aiohttp.ClientSession, bot, lang_dir: str, base_url: str, ckey: str):
    zip_path = os.path.join(bot.i18n_dir, 'i18n_resources.zip')
    async with session.get(f'{base_url}/download/all.zip?key={ckey}') as resp:
        resp.raise_for_status()
        async with aiofiles.open(zip_path, mode='wb+') as f:
            while True:
                chunk = await resp.content.read(1024)
                if not chunk:
                    break
                await f.write(chunk)
        logging.info('Downloaded zipfile of translations')

    try:
        for file in os.listdir(lang_dir):
            fpath = os.path.join(lang_dir, file)
            try:
                if os.path.isfile(fpath):
                    await unlink(fpath)
                elif os.path.isdir(fpath):
                    await rmtree(fpath)
            except Exception:
                logging.exception('Failed to remove %s', file)
    except FileNotFoundError:
        pass
    logging.info('Cleaned up i18n directory')

    await extract_zip(zip_path, lang_dir)
    logging.info('Extracted zipfile of translations')

    await unlink(zip_path)


async def load_languages(bot):
    bot.languages = {}
    base_url = 'https://api.crowdin.com/api/project/twitchbot'
    ckey = os.getenv('CROWDIN_KEY')
    lang_dir = os.path.join(bot.i18n_dir, 'i18n_resources')

    async with aiohttp.ClientSession() as session:
        if 'crowdin-build' not in (getenv('SC_DISABLED_FEATURES') or []):
            async with session.get(f'{base_url}/export?key={ckey}') as resp:
                resp.raise_for_status()
                logging.info('Built Crowdin translations')

        if 'crowdin-pull' not in (getenv('SC_DISABLED_FEATURES') or []):
            await pull_languages(
                session=session,
                bot=bot,
                lang_dir=lang_dir,
                base_url=base_url,
                ckey=ckey)

        for file in os.listdir(lang_dir):
            fpath = os.path.join(lang_dir, file)
            if os.path.isdir(fpath):
                json_fpath = os.path.join(fpath, 'main.json')
                async with aiofiles.open(json_fpath, 'r', encoding='utf-8') as f:
                    content = json.loads(await f.read())
                    if os.getenv('ENABLE_PRO_FEATURES') == '1':
                        content = replace_prefixes(content)

                    bot.languages[file] = content
                    logging.debug('Loaded language %s', file)

        logging.info('Loaded %i languages (%s bytes)', len(bot.languages), sys.getsizeof(bot.languages))
