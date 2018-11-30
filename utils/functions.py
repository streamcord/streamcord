from . import settings
from .exceptions import TooManyRequestsError
import requests
import time
import logging
import asyncio, aiohttp
import datadog

stream_token = {}
token = {}

def obtain_access_token():
    r = requests.post('https://id.twitch.tv/oauth2/token', params={"client_id": settings.Twitch.ID, "client_secret": settings.Twitch.SECRET, "grant_type": "client_credentials"})
    if r.status_code > 399:
        print('Error {} while getting access token:\n{}'.format(str(r.json())))
        return {}
    return r.json()

def TWAPI_REQUEST(url):
    global token
    if token.get('expires_in', 0) + time.time() <= time.time() + 1:
         token = obtain_access_token()
    headers = {
        "Client-ID": settings.Twitch.ID,
        "Authorization": "Bearer " + token.get('access_token'),
        "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.VERSION),
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    r = requests.get(url, headers=headers)
    logging.info("GET {0.url} {0.status_code} remaining {1}".format(r, r.headers.get('Ratelimit-Remaining')))
    if r.status_code == 429:
        raise TooManyRequestsError
    elif r.status_code != 200:
        TRIGGER_WEBHOOK("GET {0.url} {0.status_code}".format(r))
    if not settings.BETA:
        datadog.statsd.increment('bot.twapi_calls', tags=["bucket:reg"])
    return r
"""
def obtain_stream_access_token():
    r = requests.post('https://id.twitch.tv/oauth2/token', params={"client_id": settings.Twitch.STREAM_ID, "client_secret": settings.Twitch.STREAM_SECRET, "grant_type": "client_credentials"})
    if r.status_code > 399:
        print('Error {} while getting access token:\n{}'.format(r.status_code, str(r.json())))
        return {}
    return r.json()
"""

async def obtain_stream_access_token(bot):
    params = {
        "client_id": settings.Twitch.STREAM_ID,
        "client_secret": settings.Twitch.STREAM_SECRET,
        "grant_type": "client_credentials"
    }
    async with bot.aiohttp.post('https://id.twitch.tv/oauth2/token', params=params) as r:
        if r.status > 399:
            logging.error('Error {} while getting access token:\n{}'.format(r.status, str(await r.json())))
            return {}
        return await r.json()

async def stream_request(bot, url):
    global stream_token
    if stream_token.get('expires_in', 0) + time.time() <= time.time() + 1:
        stream_token = await obtain_stream_access_token(bot)
    headers = {
        "Client-ID": settings.Twitch.STREAM_ID,
        "Authorization": "Bearer " + stream_token.get('access_token'),
        "User-Agent": "TWMetrics (v{})".format(settings.VERSION),
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    async with bot.aiohttp.get("https://api.twitch.tv/helix" + url, headers=headers) as r:
        logging.info("GET {0.url} {0.status} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        if int(r.headers.get('RateLimit-Remaining', 1)) == 0:
            wait_time = (float(r.headers.get('RateLimit-Reset', time.time())) - time.time()) + 0.5
            logging.info("Ratelimit hit... Waiting {} second(s) before continuing".format(str(wait_time)))
            await asyncio.sleep(wait_time)
        if not settings.BETA:
            datadog.statsd.increment('bot.twapi_calls', tags=["bucket:stream"])
        return await r.json()
"""
async def STREAM_REQUEST(bot, url):
    global stream_token
    if stream_token.get('expires_in', 0) + time.time() <= time.time() + 1:
        stream_token = obtain_stream_access_token()
    headers = {
        "Client-ID": settings.Twitch.STREAM_ID,
        "Authorization": "Bearer " + stream_token.get('access_token'),
        "User-Agent": "TWMetrics (v{})".format(settings.VERSION),
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    r = requests.get("https://api.twitch.tv/helix" + url, headers=headers)
    logging.info("GET {0.url} {0.status_code} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
    if r.status_code > 499:
        await asyncio.sleep(5)
        r = requests.get("https://api.twitch.tv/helix" + url, headers=headers)
        logging.info("GET {0.url} {0.status_code} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
    if int(r.headers.get('RateLimit-Remaining', 1)) == 0:
        wait_time = (float(r.headers.get('RateLimit-Reset', time.time())) - time.time()) + 0.5
        logging.info("Ratelimit hit... Waiting {} second(s) before continuing".format(str(wait_time)))
        await asyncio.sleep(wait_time)
    if not settings.BETA:
        datadog.statsd.increment('bot.twapi_calls', tags=["bucket:stream"])
    return r
"""
def DBOTS_REQUEST(url):
    headers = {
        "Authorization": settings.BotList.DISCORDBOTS,
        "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.VERSION)
    }
    r = requests.get("https://discordbots.org/api" + url, headers=headers)
    logging.info("GET {0.url} {0.status_code}".format(r))
    if r.status_code == 429:
        raise TooManyRequestsError
    return r

def OWAPI_REQUEST(url):
    headers = {
        "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.VERSION)
    }
    r = requests.get("https://owapi.net/api/v3" + url, headers=headers, timeout=40)
    return r

async def TRN_FORTNITE_REQUEST(self, url):
    if self.bot.ratelimits['fortnite'] + 1 > time.time():
        await asyncio.sleep(2)
    self.bot.ratelimits['fortnite'] = time.time()
    headers = {
        "TRN-Api-Key": settings.TRN.FORTNITE_SECRET,
        "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.VERSION)
    }
    r = requests.get("https://api.fortnitetracker.com/v1/profile" + url, headers=headers)
    return r

async def TRN_PUBG_REQUEST(self, url):
    if self.bot.ratelimits['fortnite'] + 1 > time.time():
        await asyncio.sleep(2)
    self.bot.ratelimits['fortnite'] = time.time()
    headers = {
        "TRN-Api-Key": settings.TRN.PUBG_SECRET,
        "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.VERSION)
    }
    r = requests.get("https://api.pubgtracker.com/v2" + url, headers=headers)

async def RLS_REQUEST(self, url):
    if self.bot.ratelimits['rocketleague'] + 0.5 > time.time():
        await asyncio.sleep(0.5)
    self.bot.ratelimits['rocketleague'] = time.time()
    headers = {
        "Authorization": settings.RLS.SECRET,
        "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.VERSION)
    }
    r = requests.get("https://api.rocketleaguestats.com/v1" + url, headers=headers)
    return r

def GET_UPTIME(u):
    t = time.time() - u
    st = time.gmtime(t)
    return "{1} days, {0.tm_hour} hours, and {0.tm_min} minutes".format(st, st.tm_mday - 1)

def SPLIT_EVERY(time, iterable):
    items = []
    current_item = {}
    if len(iterable) < time + 1:
        return [iterable]
    for i in iterable.keys():
        if len(current_item) > time - 1:
            items.append(current_item)
            current_item = {}
        current_item[i] = iterable[i]
    if current_item != {}:
        items.append(current_item)
    return items

def FORMAT_OWAPI_USER(username):
    u = username.replace("#", "-").replace(" ", "_")
    """fmt = ""
    for let in u:
        for l in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_-":
            if let in l:
                fmt += let
    return fmt"""
    return u

def TRIGGER_WEBHOOK(msg):
    payload = {"content": msg.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")}
    r = requests.post("https://canary.discordapp.com/api/webhooks/508286400572030991/qNeJ3N3-DVQj4tZq88n4we_EiFIOpP4lIGsc5sZrx_nCSw7XMO6UDH8QHIZhYaxGf6Eo", data=payload)
    if r.status_code > 299:
        logging.error("Webhook failed with status of " + str(r.status_code))
    return r

def replace_all(text, dic):
    for i, j in dic.items():
        text = text.replace(str(i), str(j))
    return text
