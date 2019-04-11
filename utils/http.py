from . import settings, functions
import requests
import asyncio, aiohttp
import logging
import discord
import time
import datadog
import textwrap

stream_token = {}
token = {}

def ObtainAccessToken():
    r = requests.post('https://id.twitch.tv/oauth2/token', params={
        "client_id": settings.Twitch.ClientID,
        "client_secret": settings.Twitch.Secret,
        "grant_type": "client_credentials"
    })
    if r.status_code > 399:
        print('Error {} while getting access token:\n{}'.format(str(r.json())))
        return {}
    logging.info(f'Obtained access token')
    return r.json()

def TwitchAPIRequest(url):
    global token
    if token.get('expires_in', 0) + time.time() <= time.time() + 1:
         token = ObtainAccessToken()
    headers = {
        "Client-ID": settings.Twitch.ClientID,
        "Authorization": "Bearer " + token.get('access_token'),
        "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.Version),
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 429:
        raise TooManyRequestsError
    elif r.status_code != 200:
        logging.warn("GET {0.url} {0.status_code} remaining {1}".format(r, r.headers.get('Ratelimit-Remaining')))
    else:
        logging.debug("GET {0.url} {0.status_code} remaining {1}".format(r, r.headers.get('Ratelimit-Remaining')))
    if not settings.UseBetaBot:
        datadog.statsd.increment('bot.twapi_calls', tags=["bucket:reg"])
    return r

async def AsyncObtainAccessToken(bot, is_stream=False):
    params = {
        "client_id": settings.Twitch.ClientID,
        "client_secret": settings.Twitch.Secret,
        "grant_type": "client_credentials"
    }
    if is_stream == True:
        params = {
            "client_id": settings.Twitch.StreamClientID,
            "client_secret": settings.Twitch.StreamSecret,
            "grant_type": "client_credentials"
        }
    async with bot.aiohttp.post('https://id.twitch.tv/oauth2/token', params=params) as r:
        if r.status > 399:
            logging.error('Error {} while getting access token:\n{}'.format(r.status, str(await r.json())))
            return {}
        logging.info(f'Obtained access token (stream={is_stream})')
        return await r.json()

async def AsyncTwitchAPIRequest(bot, url):
    global token
    if token.get('expires_in', 0) + time.time() <= time.time() + 1:
         token = await AsyncObtainAccessToken(bot)
    headers = {
        "Client-ID": settings.Twitch.ClientID,
        "Authorization": "Bearer " + token.get('access_token'),
        "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.Version),
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    async with bot.aiohttp.get(url, headers=headers) as r:
        if r.status > 399:
            logging.warn("GET {0.url} {0.status} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        else:
            logging.debug("GET {0.url} {0.status} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        if not settings.UseBetaBot:
            datadog.statsd.increment('bot.twapi_calls', tags=["bucket:reg"])
        if r.status == 429:
            raise TooManyRequestsError
        return r

async def AsyncTwitchAPIStreamRequest(bot, url):
    global stream_token
    if stream_token.get('expires_in', 0) + time.time() <= time.time() + 1:
        stream_token = await AsyncObtainAccessToken(bot, is_stream=True)
    headers = {
        "Client-ID": settings.Twitch.StreamClientID,
        "Authorization": "Bearer " + stream_token.get('access_token'),
        "User-Agent": "TWMetrics (v{})".format(settings.Version),
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    async with bot.aiohttp.get("https://api.twitch.tv/helix" + url, headers=headers) as r:
        if r.status > 399:
            logging.warn("GET {0.url} {0.status} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        else:
            logging.debug("GET {0.url} {0.status} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        if int(r.headers.get('RateLimit-Remaining', 1)) == 0:
            wait_time = (float(r.headers.get('RateLimit-Reset', time.time())) - time.time()) + 0.5
            logging.info("Ratelimit hit... Waiting {} second(s) before continuing".format(str(wait_time)))
            await asyncio.sleep(wait_time)
        if not settings.UseBetaBot:
            datadog.statsd.increment('bot.twapi_calls', tags=["bucket:stream"])
        return await r.json()

async def SendMetricsWebhook(msg):
    msg = functions.ReplaceAllInStr(msg, {"@everyone": "@\u200beveryone", "@here": "@\u200bhere"})
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(settings.WebhookURL, adapter=discord.AsyncWebhookAdapter(session))
        await webhook.send(msg)

class oAuth:
    async def NewTwitchOAuthToken(oauthinfo, aio_session, uid, nested=False):
        async with aio_session as session:
            async with aiohttp.ClientSession() as session:
                params = {
                    "client_id": settings.Twitch.ClientID,
                    "client_secret": settings.Twitch.Secret,
                    "grant_type": "refresh_token",
                    "refresh_token": oauthinfo['refresh_token']
                }
                resp = None
                async with session.post('https://id.twitch.tv/oauth2/token', params=params) as r:
                    if r.status > 299:
                        if not nested:
                            await asyncio.sleep(1)
                            return NewTwitchOAuthToken(oauthinfo, aio_session, nested=True)
                        else:
                            raise requests.exceptions.ConnectionError("unable to get access token:\n{}".format(await r.text()))
                    resp = await r.json()
                    params = {
                        "access_token": resp['access_token'],
                        "refresh_token": resp['refresh_token']
                    }
                async with session.post('https://dash.twitchbot.io/api/connections/{}/token'.format(uid), headers={"X-Access-Token": settings.Twitch.ClientID}, params=params):
                    if r.status > 299:
                        logging.error('failed to update token info to dashboard ({}):\n{}'.format(r.status, await r.text()))
                return resp

    async def TwitchAPIOAuthRequest(url, oauthinfo, uid, nested=False):
        async with aiohttp.ClientSession() as session:
            headers = {
                "Client-ID": settings.Twitch.ClientID,
                "Authorization": "OAuth " + oauthinfo['access_token']
            }
            async with session.get(url, headers=headers) as r:
                if r.status in [401, 403]:
                    if not nested:
                        code = await NewTwitchOAuthToken(oauthinfo, session, uid)
                        return TwitchAPIOAuthRequest(url, code, uid, nested=True)
                    else:
                        raise requests.exceptions.ConnectionError("failed to get url {} ({}):\n{}".format(r.url, r.status, await r.text()))
                elif r.status > 499:
                    if not nested:
                        return TwitchAPIOAuthRequest(url, oauthinfo, uid, nested=True)
                    else:
                        raise requests.exceptions.ConnectionError("failed to get url {} ({}):\n{}".format(r.url, r.status, await r.text()))
                return r

class Games:
    def IGDBSearchGame(query):
        payload = textwrap.dedent(f"""\
        search "{query}";
        limit 1;
        fields first_release_date,follows,popularity,rating,rating_count,status,summary,slug;
        """)
        r = requests.post('https://api-v3.igdb.com/games', headers={"user-key": settings.IGDB, "content-type": "text/plain"}, data=payload)
        return r

    def OverwatchAPIRequest(url):
        headers = {
            "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.Version)
        }
        r = requests.get(f"https://owapi.net/api/v3{url}", headers=headers)
        return r

    async def TRNFortniteRequest(self, url):
        headers = {
            "TRN-Api-Key": settings.TRN.FortniteAPISecret,
            "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.Version)
        }
        r = requests.get("https://api.fortnitetracker.com/v1/profile" + url, headers=headers)
        return r

    async def TRNPUBGRequest(self, url):
        headers = {
            "TRN-Api-Key": settings.TRN.PUBGAPISecret,
            "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.Version)
        }
        r = requests.get("https://api.pubgtracker.com/v2" + url, headers=headers)

class BotLists:
    def DBLRequest(url):
        headers = {
            "Authorization": settings.BotList.DiscordBotsORG,
            "User-Agent": "TwitchBot (https://twitchbot.io, v{})".format(settings.Version)
        }
        r = requests.get("https://discordbots.org/api" + url, headers=headers)
        if r.status_code > 399:
            logging.warn("GET {0.url} {0.status_code} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        else:
            logging.debug("GET {0.url} {0.status_code} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        if r.status_code == 429:
            raise TooManyRequestsError
        return r
