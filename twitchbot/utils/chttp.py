import asyncio
from json import loads
import logging
from math import ceil
from os import getenv
import time

import aiohttp
import discord
from . import functions


# pylint: disable=too-few-public-methods
class exceptions:
    class HTTPError(Exception):
        pass

    class RatelimitExceeded(Exception):
        pass


class CHTTPResponse:
    def __init__(self, aiorequest, text):
        self._aiorequest = aiorequest
        self._text = text

    @staticmethod
    async def make(aiorequest):
        return CHTTPResponse(
            aiorequest,
            await aiorequest.text())

    async def json(self):
        return loads(self._text)

    def raise_for_status(self):
        if self._aiorequest.status > 399:
            raise exceptions.HTTPError(f'Request failed with status code {self._aiorequest.status}')

    @property
    def status(self):
        return self._aiorequest.status

    async def text(self):
        return self._text


class BaseCHTTP:
    def __init__(self, bot):
        self.aiohttp = aiohttp.ClientSession()
        self.bot = bot
        self.logger = logging.getLogger('chttp.base')
        self.webhook = discord.Webhook.from_url(
            getenv('METRIC_WEBHOOK_URL'),
            adapter=discord.AsyncWebhookAdapter(self.aiohttp))

    async def post_metrics_webhook(self, message):
        message = functions.replace_multiple(
            message, {"@everyone": "@\u200beveryone", "@here": "@\u200bhere"})
        return await self.webhook.send(message)

    async def internal_api_get(self, url):
        async with self.aiohttp.get(url, headers={'X-Auth-Key': getenv('DASHBOARD_KEY')}) as re:
            self.logger.debug('GET %s%s %i', re.url.host, re.url.path, re.status)
            return await CHTTPResponse.make(re)

    async def search_game_igdb(self, query, fields=None):
        if fields is None:
            fields = 'first_release_date,follows,popularity,rating,rating_count,status,summary,slug'
        payload = f'search "{query}";limit 1;fields {fields};'
        async with self.aiohttp.post(
                'https://api-v3.igdb.com/games',
                headers={'user-key': getenv('IGDB_KEY'), 'content-type': 'text/plain'},
                data=payload
        ) as re:
            self.logger.debug('POST %s%s %i', re.url.host, re.url.path, re.status)
            return await CHTTPResponse.make(re)

    async def dbl_api_get(self, url):
        async with self.aiohttp.get(
                f'https://discordbots.org/api{url}',
                headers={'Authorization': getenv('BOTLIST_TOKEN')}
        ) as re:
            self.logger.debug('GET %s%s %i', re.url.host, re.url.path, re.status)
            return await CHTTPResponse.make(re)

    async def get_twitch_api_status(self) -> list:
        """
        Get a list of statuses for Twitch API components. See https://devstatus.twitch.tv/
        """
        async with self.aiohttp.get('https://cjn0pxg8j9zv.statuspage.io/api/v2/summary.json') as req:
            req.raise_for_status()
            res = await req.json()
            return res['components']


class TwitchCHTTP:
    def __init__(self, bot, is_backend=False):
        # is_backend should be True if the client is to be used for the
        # internal notification loop, and False for HTTP requests in commands
        self.is_backend = is_backend

        self.aiohttp = aiohttp.ClientSession()
        self.base_url = 'https://api.twitch.tv/helix'
        self.bot = bot
        self.logger = logging.getLogger('chttp.stream' if is_backend else 'chttp.twitch')
        self.token = {}

        if not self.is_backend:
            prefix = 'TWITCH'
            bucket = 'reg'
        elif self.bot.cluster_index <= 3:
            prefix = 'TWITCH_S1'
            bucket = 'stream'
        elif self.bot.cluster_index <= 7:
            prefix = 'TWITCH_S2'
            bucket = 'stream_alt'
        elif self.bot.cluster_index <= 11:
            prefix = 'TWITCH_S3'
            bucket = 'stream_alt_2'
        else:  # elif self.bot.cluster_index <= 15:
            prefix = 'TWITCH_S4'
            bucket = 'stream_alt_3'
        self.client_config = (
            {
                'client_id': getenv(f'{prefix}_CLIENT_ID'),
                'client_secret': getenv(f'{prefix}_SECRET'),
                'grant_type': 'client_credentials'
            },
            f'bucket:{bucket}'
        )

    @property
    def base_headers(self):
        return {
            'Accept': 'application/vnd.twitchtv.v5+json',
            'Authorization': f'Bearer {self.token.get("access_token")}',
            'Client-ID': self.client_config[0]['client_id'],
            'User-Agent': f'Streamcord (https://streamcord.io, v{getenv("VERSION")})'
        }

    async def _get_access_token(self):
        """
        Obtain an App Access Token from Twitch's OAuth Client Credentials Flow.
        https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#oauth-client-credentials-flow
        """

        params, bucket = self.client_config
        async with self.aiohttp.post('https://id.twitch.tv/oauth2/token', params=params) as re:
            if re.status > 399:
                self.logger.exception('Error %i while getting access token', re.status)
                self.logger.fatal('%s', await re.text())
                self.token = {}

            token = await re.json()
            try:
                token['expires_in'] += time.time()
            except KeyError:
                # probably shouldn't need this, but catch just in case
                self.logger.warning('Failed to set token expiration time')

            self.logger.info(
                'Obtained access token (is_backend:%s,%s) %s',
                self.is_backend,
                bucket,
                str(token).replace(token['access_token'], '[REDACTED]'))
            self.token = token

    async def get(self, url, params=None, is_v5=False):
        """
        Perform an HTTP GET request on the Twitch API.
        """

        _, bucket = self.client_config
        if self.token.get('expires_in', 0) <= time.time() + 1 or not self.token:
            await self._get_access_token()

        ctime = time.time()
        async with self.aiohttp.get(
                f'{"https://api.twitch.tv/kraken" if is_v5 else self.base_url}{url}',
                headers=self.base_headers,
                params=params
        ) as re:
            self.logger.debug(
                'GET %s%s %i (%ims)',
                re.url.host, re.url.path, re.status, round((time.time() - ctime) * 1000))
            if re.status > 399:
                self.logger.fatal('%s', await re.text())

            if int(re.headers.get('RateLimit-Remaining', 99)) <= 5 and re.status == 200:
                bucket_reset = float(re.headers.get('RateLimit-Reset', time.time()))
                wait_time = ceil(bucket_reset - time.time() + 0.5)
                self.logger.warning('Ratelimit bucket exhausted, waiting %is', wait_time)
                await asyncio.sleep(wait_time)

            await functions.dogstatsd.increment(
                'bot.twapi_calls',
                tags=[bucket, f'status:{re.status}', f'endpoint:{re.url.path}'])

            return await CHTTPResponse.make(re)
