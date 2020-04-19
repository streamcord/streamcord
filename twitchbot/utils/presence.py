import aiohttp
import json
import logging
from os import getenv

from rethinkdb import RethinkDB
from typing import Tuple
from .functions import dogstatsd

r = RethinkDB()


async def request_api(path: str, *, method: str = 'GET', params: dict = None, data: any = None) -> Tuple[dict, int]:
    headers = {
        'Host': 'api.streamcord.io',
        'X-Auth-Key': getenv('DASHBOARD_KEY')
    }
    async with aiohttp.ClientSession() as session:
        async with session.request(method, f'http://{getenv("LAVALINK_HOST")}{path}', headers=headers, params=params, data=data) as req:
            return req.status


async def post_stats(bot):
    # FIXME: update this endpoint
    async with aiohttp.ClientSession() as session:
        payload = {
            "cluster_index": bot.cluster_index,
            "guild_count": len(bot.guilds),
            "member_count": len(list(bot.get_all_members())),
            "active_voice_sessions": len(bot.active_vc),
            "latencies": bot.latencies,
            "total_shards": bot.shard_count
        }
        if bot.cluster_index == 0:
            await dogstatsd.gauge(
                'bot.notifications',
                value=(await r.table('notifications').count().run(bot.rethink)))
            await dogstatsd.gauge(
                'bot.live_checks',
                value=0)
        headers = {
            "Host": "api.streamcord.io",
            "X-Auth-Key": getenv('DASHBOARD_KEY')
        }
        async with session.post(
                f"http://{getenv('LAVALINK_HOST')}/metrics",
                data=json.dumps(payload),
                headers=headers
        ) as re:
            if not re.status == 200:
                t = await re.text()
                logging.error('Failed to post cluster stats (%i): %s', re.status, t)
            else:
                logging.info("Posted cluster stats")


async def post_connect_event(cluster_id: int):
    await request_api('/v2/events/connect', method='POST', params={'cluster_id': cluster_id + 1})


async def post_disconnect_event(cluster_id: int):
    await request_api('/v2/events/disconnect', method='POST', params={'cluster_id': cluster_id + 1})


async def post_ready_event(cluster_id: int):
    await request_api('/v2/events/ready', method='POST', params={'cluster_id': cluster_id + 1})


async def post_shard_ready_event(shard_id: int):
    await request_api('/v2/events/shard-ready', method='POST', params={'shard_id': shard_id})
