import asyncio
import discord
import aiohttp
import json
from . import settings
import logging
import time, datetime
import datadog
import rethinkdb as r
r = r.RethinkDB()


async def change_presence(bot):
    if settings.UseBetaBot:
        await bot.change_presence(status=discord.Status.idle, activity=discord.Game("with new features"))
    else:
        await bot.change_presence(activity=discord.Streaming(name="!twitch help · twitchbot.io", url="https://twitch.tv/twitchbot_discord"))


async def post_stats(bot):
    async with aiohttp.ClientSession() as session:
        clindex = round(min(bot.shard_ids)/10)  # 10 shards per cluster
        payload = {
            "cluster_index": clindex,
            "guild_count": len(bot.guilds),
            "member_count": len(list(bot.get_all_members())),
            "active_voice_sessions": len(bot.active_vc),
            "latencies": bot.latencies,
            "total_shards": bot.shard_count
        }
        if payload['cluster_index'] == 0:
            datadog.statsd.open_buffer()
            datadog.statsd.gauge(
                'bot.notifications',
                r.table('notifications').count().run(bot.rethink, durability="soft")
            )
            datadog.statsd.gauge(
                'bot.live_checks',
                r.table('live_role').count().run(bot.rethink, durability="soft")
            )
            datadog.statsd.close_buffer()
        headers = {
            "X-Auth-Key": settings.DashboardKey
        }
        async with session.post("https://api.twitchbot.io/metrics", data=json.dumps(payload), headers=headers) as re:
            if not re.status == 200:
                t = await re.text()
                logging.error(f"Failed to post cluster stats ({re.status}): {t}")
            else:
                logging.info("Posted cluster stats")
