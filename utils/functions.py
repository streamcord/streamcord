from . import settings
from .exceptions import TooManyRequestsError
import requests
import time
import logging

def TRIGGER_WEBHOOK(msg):
    r = requests.post("https://canary.discordapp.com/api/webhooks/webhook_id/webhook_token", data={"content": msg})
    return r

def TWAPI_REQUEST(url):
    headers = {
        "Client-ID": settings.Twitch.ID,
        "Authentication": "Bearer " + settings.Twitch.SECRET,
        "User-Agent": "TwitchBot (https://twitch.disgd.pw, v{})".format(settings.VERSION),
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    r = requests.get(url, headers=headers)
    logging.info("GET {0.url} {0.status_code}".format(r))
    if r.status_code == 429:
        raise TooManyRequestsError
    elif r.status_code != 200:
        TRIGGER_WEBHOOK("GET {0.url} {0.status_code}".format(r))
    return r

async def STREAM_REQUEST(bot, url):
    if bot.ratelimits['twitch'] > time.time():
        await asyncio.sleep(bot.ratelimits['twitch'] - time.time())
    headers = {
        "Client-ID": settings.Twitch.STREAM_ID,
        "Authentication": "Bearer " + settings.Twitch.STREAM_SECRET,
        "User-Agent": "TWMetrics (v{})".format(settings.VERSION),
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    r = requests.get("https://api.twitch.tv/helix" + url, headers=headers)
    logging.info("GET {0.url} {0.status_code}".format(r))
    if r.status_code == 429 or int(r.headers.get('RateLimit-Remaining')) < 2:
        bot.ratelimits['twitch'] = r.headers.get('RateLimit-Reset')
        raise TooManyRequestsError
    elif r.status_code != 200:
        TRIGGER_WEBHOOK("GET {0.url} {0.status_code}".format(r))
    return r

def DBOTS_REQUEST(url):
    headers = {
        "Authorization": settings.BotList.DBL,
        "User-Agent": "TwitchBot (https://twitch.disgd.pw, v{})".format(settings.VERSION)
    }
    r = requests.get("https://discordbots.org/api" + url, headers=headers)
    logging.info("GET {0.url} {0.status_code}".format(r))
    if r.status_code == 429:
        raise TooManyRequestsError
    return r

def OWAPI_REQUEST(url):
    headers = {
        "User-Agent": "TwitchBot (https://twitch.disgd.pw, v{})".format(settings.VERSION)
    }
    r = requests.get("https://owapi.net/api/v3" + url, headers=headers)
    return r

async def TRN_FORTNITE_REQUEST(self, url):
    if self.bot.ratelimits['fortnite'] + 1 > time.time():
        await asyncio.sleep(2)
    self.bot.ratelimits['fortnite'] = time.time()
    headers = {
        "TRN-Api-Key": settings.TRN.FORTNITE_SECRET,
        "User-Agent": "TwitchBot (https://twitch.disgd.pw, v{})".format(settings.VERSION)
    }
    r = requests.get("https://api.fortnitetracker.com/v1/profile" + url, headers=headers)
    return r

async def TRN_PUBG_REQUEST(self, url):
    if self.bot.ratelimits['fortnite'] + 1 > time.time():
        await asyncio.sleep(2)
    self.bot.ratelimits['fortnite'] = time.time()
    headers = {
        "TRN-Api-Key": settings.TRN.PUBG_SECRET,
        "User-Agent": "TwitchBot (https://twitch.disgd.pw, v{})".format(settings.VERSION)
    }
    r = requests.get("https://api.pubgtracker.com/v2" + url, headers=headers)

async def RLS_REQUEST(self, url):
    if self.bot.ratelimits['rocketleague'] + 0.5 > time.time():
        await asyncio.sleep(0.5)
    self.bot.ratelimits['rocketleague'] = time.time()
    headers = {
        "Authorization": settings.RLS.SECRET,
        "User-Agent": "TwitchBot (https://twitch.disgd.pw, v{})".format(settings.VERSION)
    }
    r = requests.get("https://api.rocketleaguestats.com/v1" + url, headers=headers)
    return r

def GET_UPTIME(u):
    t = time.time() - u
    st = time.gmtime(t)
    return "{1} days, {0.tm_hour} hours, and {0.tm_min} minutes".format(st, st.tm_mday - 1)
