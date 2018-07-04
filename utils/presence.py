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

def send_help_content(ctx, bot):
    e = discord.Embed(color=discord.Color(0x6441A4))
    e.set_author(icon_url=bot.user.avatar_url, name="TwitchBot Help", url="https://twitch.disgd.pw/")
    e.set_thumbnail(url=bot.user.avatar_url)
    e.description = "Hello! <:twitch:404633403603025921> I'm a bot that helps integrate Discord servers with Twitch."
    e.add_field(name="Commands", value="To view a list of all commands, type `twitch commands`.")
    e.add_field(name="Support", value="Found an error, or having trouble with the bot? Join the Discord [here](https://discordapp.com/invite/UNYzJqV) and the support team will assist you.")
    e.add_field(name="Invite", value="[Click here](https://discordapp.com/oauth2/authorize?client_id=375805687529209857&permissions=8&scope=bot&response_type=code&redirect_uri=https://twitch.disgd.pw/thanks.html) to invite me to your Discord server.")
    e.add_field(name="Website", value="You can view my website at https://twitch.disgd.pw.")
    e.add_field(name="FAQ", value="Some of the most frequently asked questions and answers are listed [here](https://twitch.disgd.pw/how-to.html).")
    e.add_field(name="Upvote", value="[Upvote me on DBL](https://discordbots.org/bot/twitch/vote) to get access to audio.")
    e.add_field(name="Donate", value="Want to help keep me running on Discord, and get a couple rewards for doing so? Visit my Patreon at https://patreon.com/devakira.")
    e.add_field(name="About", value="To see statistics and more, type `twitch info`. I was made by Akira#4587 with discord.py rewrite.")
    e.set_footer(icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url, text=str(ctx.author))
    return e

def send_commands_content():
    e = discord.Embed(color=discord.Color(0x6441A4), title="<:twitch:404633403603025921> TwitchBot Commands")
    e.description = "**Do not put `<>` or `[]` around command arguments.**"
    e.add_field(name="General", value="""
`twitch help` - Shows bot help
`twitch info` - Shows bot info
`twitch invite` - Displays a link to add TwitchBot to your server
`twitch status` - Shows bot status
`twitch ping` - Pong!
""", inline=False)
    e.add_field(name="Twitch", value="""
`twitch user <user>` - Gets info on a Twitch channel
`twitch stream user <user>` - Gets info on a user's stream
`twitch stream watch <user>` - Watch a Twitch stream from Discord
`twitch stream top` - Fetches info on a top stream
`twitch game <name>` - Gets info on a Twitch game
`twitch top` - Gets the most popular Twitch games
    """, inline=False)
    e.add_field(name="Clips", value="""
`twitch clips from <user>` - Gets a clip from the specified Twitch user
`twitch clips trending` - Gets a trending clip
`twitch clips game <game>` - Gets a clip from the specified game
    """, inline=False)
    e.add_field(name="Streamer Notifications & Live Users", value="""
`twitch notif add <#discord_channel> <twitch_username> [message]` - Adds a streamer notification for a streamer to the specified channel
`twitch notif remove <#discord_channel> <twitch_username> [message]` - Remove a streamer notification for a streamer to the specified channel
`twitch notif list [#discord_channel]` - Lists the streamer notifications for the specified channel
`twitch live_check <role_name>` - Adds the specified role to users when they go live on Twitch, and then removes the role when they stop streaming
    """, inline=False)
    e.add_field(name="Audio", value="""
`twitch listen <user>` - Listen to a Twitch stream in the current voice channel
`twitch nowplaying` - Shows the stream currently playing, if any
`twitch leave` - Leaves a voice channel
    """, inline=False)
    e.add_field(name="Moderation", value="""
`twitch ban <@user> [reason]` - Bans a user with an optional reason
`twitch kick <@user> [reason]` - Kicks a user with an optional reason
`twitch purge <amt>` - Bulk-deletes the specified amount of messages from the current channel
`twitch filter set <sensitivity>` - Sets the server-wide toxicity filter
`twitch filter remove` - Removes the server-wide toxicity filter
    """, inline=False)
    e.add_field(name="Game Stats", value="""
`twitch overwatch <pc/psn/xbl> <player>` - Shows Overwatch player stats
`twitch fortnite <pc/psn/xbl> <player>` - Shows Fortnite player stats
`twitch rl <pc/psn/xbl> <player>` - Shows Rocket League player stats
    """)
    return e
