import json
import logging
from os import getenv

import aiohttp
from rethinkdb import RethinkDB

from .functions import dogstatsd

r = RethinkDB()


async def post_stats(bot):
    async with aiohttp.ClientSession() as session:
        payload = {
            "cluster_index": bot.cluster_index,
            "guild_count": len(bot.guilds),
            "member_count": len(list(bot.get_all_members())),
            "active_voice_sessions": len(bot.active_vc),
            "latencies": bot.latencies,
            "total_shards": bot.shard_count
        }
        if payload['cluster_index'] == 0:
            await dogstatsd.gauge(
                'bot.notifications',
                value=(await r.table('notifications').count().run(bot.rethink)))
            await dogstatsd.gauge(
                'bot.live_checks',
                value=(await r.table('live_role').count().run(bot.rethink)))
        headers = {
            "X-Auth-Key": getenv('DASHBOARD_KEY')
        }
        async with session.post(
                "https://api.twitchbot.io/metrics",
                data=json.dumps(payload),
                headers=headers
        ) as re:
            if not re.status == 200:
                t = await re.text()
                logging.error('Failed to post cluster stats (%i): %s', re.status, t)
            else:
                logging.info("Posted cluster stats")
