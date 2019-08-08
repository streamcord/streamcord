from . import settings, functions
import requests
import asyncio
import aiohttp
import logging
import discord
import time
import math
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
    try:
        r.raise_for_status()
    except Exception:
        logging.exception("Failed to get Twitch access token!!!")
        logging.error(r.json())
        return {}
    else:
        logging.info(f'Obtained access token')
    return r.json()


def TwitchAPIRequest(url):
    global token
    if token.get('expires_in', 0) + time.time() <= time.time() + 1:
        token = ObtainAccessToken()
    headers = {
        "Client-ID": settings.Twitch.ClientID,
        "Authorization": "Bearer " + token.get('access_token'),
        "User-Agent": f"TwitchBot (https://twitchbot.io, v{settings.Version})",
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
        datadog.statsd.increment(
            'bot.twapi_calls',
            tags=[
                "bucket:reg",
                f"status:{r.status_code}"
            ]
        )
    return r


def GetTwitchClient(bot, is_stream):
    cluster = bot.cluster_index
    if (is_stream is False):
        return {
            "client_id": settings.Twitch.ClientID,
            "client_secret": settings.Twitch.Secret,
            "grant_type": "client_credentials"
        }, "bucket:reg"
    elif cluster <= 3:
        return {
            "client_id": settings.Twitch.StreamClientID,
            "client_secret": settings.Twitch.StreamSecret,
            "grant_type": "client_credentials"
        }, "bucket:stream"
    elif cluster <= 7:
        return {
            "client_id": settings.Twitch.Stream1ClientID,
            "client_secret": settings.Twitch.Stream1Secret,
            "grant_type": "client_credentials"
        }, "bucket:stream_alt"
    else:
        return {
            "client_id": settings.Twitch.Stream2ClientID,
            "client_secret": settings.Twitch.Stream2Secret,
            "grant_type": "client_credentials"
        }, "bucket:stream_alt_2"


async def AsyncObtainAccessToken(bot, is_stream=False):
    params, bucket = GetTwitchClient(bot, is_stream)
    async with bot.aiohttp.post('https://id.twitch.tv/oauth2/token', params=params) as r:
        if r.status > 399:
            logging.fatal('Error {} while getting access token:\n{}'.format(r.status, str(await r.json())))
            return {}
        tkn = await r.json()
        try:
            tkn['expires_in'] += time.time()
        except Exception:
            logging.exception("Failed to set token expiration time")
        logging.info(
            f'Obtained access token (stream:{is_stream}) ({bucket})' +
            f': {tkn}'
        )
        return tkn


async def AsyncTwitchAPIRequest(bot, url):
    global token
    if (token.get('expires_in', 0) <= time.time() + 1) or token == {}:
        token = await AsyncObtainAccessToken(bot)

    params, bucket = GetTwitchClient(bot, False)

    headers = {
        "Client-ID": params['client_id'],
        "Authorization": "Bearer " + token.get('access_token'),
        "User-Agent": f"TwitchBot (https://twitchbot.io, v{settings.Version})",
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    async with bot.aiohttp.get(url, headers=headers) as r:
        if r.status > 399:
            logging.warn("GET {0.url} {0.status} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        else:
            logging.debug("GET {0.url} {0.status} remaining {1}".format(r, r.headers.get('RateLimit-Remaining')))
        if not settings.UseBetaBot:
            datadog.statsd.increment(
                'bot.twapi_calls',
                tags=[bucket, f"status:{r.status}"]
            )
        if r.status == 429:
            raise TooManyRequestsError
        return r


async def AsyncTwitchAPIStreamRequest(bot, url):
    global stream_token

    params, bucket = GetTwitchClient(bot, True)

    if stream_token.get('expires_in', 0) <= time.time() + 1 or stream_token == {}:
        stream_token = await AsyncObtainAccessToken(bot, is_stream=True)

    headers = {
        "Client-ID": params['client_id'],
        "Authorization": "Bearer " + stream_token.get('access_token'),
        "User-Agent": f"TwitchBot (https://twitchbot.io, v{settings.Version})",
        "Accept": "application/vnd.twitchtv.v5+json"
    }
    async with bot.aiohttp.get(f"https://api.twitch.tv/helix{url}", headers=headers) as r:
        if r.status > 399:
            logging.warn(f"GET {r.url} {r.status}")
        if int(r.headers.get('RateLimit-Remaining', 1)) <= 5:
            bucket_reset = float(r.headers.get('RateLimit-Reset', time.time()))
            wait_time = math.ceil(bucket_reset - time.time() + 0.5)
            logging.info(f"Ratelimit hit... Waiting {wait_time} second(s) before continuing\n{r.headers}")
            await asyncio.sleep(wait_time)
        if not settings.UseBetaBot:
            datadog.statsd.increment(
                'bot.twapi_calls',
                tags=[bucket, f"status:{r.status}"]
            )
        return await r.json()


async def SendMetricsWebhook(msg):
    msg = functions.ReplaceAllInStr(
        msg, {
            "@everyone": "@\u200beveryone",
            "@here": "@\u200bhere"
        }
    )
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(
            settings.WebhookURL,
            adapter=discord.AsyncWebhookAdapter(session)
        )
        await webhook.send(msg)


async def bot_api_req(url, use_dash=False):
    async with aiohttp.ClientSession() as session:
        base_url = "dash.twitchbot.io/api" if use_dash else "api.twitchbot.io"
        url = "https://" + base_url + url
        async with session.get(
            url, headers={"X-Auth-Key": settings.DashboardKey}
        ) as resp:
            json = (await resp.json())
            return json, resp.status


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
