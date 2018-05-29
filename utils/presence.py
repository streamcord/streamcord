import asyncio
import discord
import aiohttp
import json
from . import settings
import logging

async def change_presence(bot):
    await bot.change_presence(activity=discord.Streaming(name="twitch help - {} guilds".format(len(bot.guilds)), url="https://twitch.tv/kraken"))

async def post_stats(bot):
    async with aiohttp.ClientSession() as session:
        payload = {
            "shard_count": bot.shard_count,
            "server_count": len(bot.guilds)
        }
        headers = {
            "Authorization": settings.BotList.DBL,
            "Content-Type": "application/json"
        }
        async with session.post("https://discordbots.org/api/bots/{}/stats".format(bot.user.id), data=json.dumps(payload), headers=headers) as r:
            if r.status == 200:
                logging.info("Posted server count to DBL. ({} shards/{} guilds)".format(bot.shard_count, len(bot.guilds)))
            else:
                logging.error("Error posting stats to DBL.")
                logging.error("HTTP " + str(r.status))
                logging.error(str(await r.json()))

def send_help_content():
    e = discord.Embed(color=discord.Color(0x6441A4), title="<:twitch:404633403603025921> TwitchBot Help")
    e.description == "**Need support?** Join the TwitchBot Discord server at https://discord.gg/eDRnXd6"
    e.add_field(name="`General`", value="""
`twitch help` - Shows bot help
`twitch info` - Shows bot info
`twitch invite` - Displays a link to add TwitchBot to your server
`twitch status` - Shows bot status
`twitch ping` - Pong!
""", inline=False)
    e.add_field(name="`Twitch`", value="""
`twitch user <user>` - Gets info on a Twitch channel
`twitch stream <user>` - Gets info on a user's stream
`twitch watch <user>` - Watch a Twitch stream from Discord
`twitch game <name>` - Gets info on a Twitch game
`twitch top` - Gets the most popular Twitch games
    """, inline=False)
    e.add_field(name="`Clips`", value="""
`twitch clips from <user>` - Gets a clip from the specified Twitch user
`twitch clips trending` - Gets a trending clip
`twitch clips game <game>` - Gets a clip from the specified game
    """, inline=False)
    e.add_field(name="`Streamer Notifications`", value="""
`twitch notif add <#discord_channel> <twitch_username>` - Adds a streamer notification for a streamer to the specified channel
`twitch notif remove <#discord_channel> <twitch_username>` - Remove a streamer notification for a streamer to the specified channel
`twitch live_check <role_name>` - Adds the specified role to users when they go live on Twitch, and then removes the role when they stop streaming
    """, inline=False)
    e.add_field(name="`Audio`", value="""
`twitch listen <user>` - Listen to a Twitch stream in the current voice channel
`twitch nowplaying` - Shows the stream currently playing, if any
`twitch leave` - Leaves a voice channel
    """, inline=False)
    e.add_field(name="`Game Stats`", value="""
`twitch overwatch <pc/psn/xbl> <player>` - Shows Overwatch player stats
`twitch fortnite <pc/psn/xbl> <player>` - Shows Fortnite player stats
`twitch rl <pc/psn/xbl> <player>` - Shows Rocket League player stats
    """)
    e.add_field(name="`Links`", value="Discord Server: [discord.me/konomi](https://discord.me/konomi)\nWebsite: [twitch.disgd.pw](https://twitch.disgd.pw)\n**Upvote TwitchBot:** [discordbots.org](https://discordbots.org/bot/375805687529209857/vote)\n**Donate to TwitchBot:** [paypal.me/akireee](https://paypal.me/akireee)")
    e.set_footer(text="""
TwitchBot is not affiliated or endorsed by Discord, Inc. or Twitch Interactive, Inc.
    """)
    return e
