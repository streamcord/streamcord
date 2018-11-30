import asyncio
import discord
import aiohttp
import json
from . import settings
import logging
import time, datetime

async def change_presence(bot):
    if settings.BETA:
        await bot.change_presence(status=discord.Status.idle, activity=discord.Game("with new features"))
    else:
        await bot.change_presence(activity=discord.Streaming(name="!twitch help • twitchbot.io", url="https://twitch.tv/twitchbot_discord"))

async def post_stats(bot):
    async with aiohttp.ClientSession() as session:
        payload = {
            "shard_count": bot.shard_count,
            "server_count": len(bot.guilds)
        }
        headers = {
            "Authorization": settings.BotList.DISCORDBOTS,
            "Content-Type": "application/json"
        }
        async with session.post("https://discordbots.org/api/bots/375805687529209857/stats", data=json.dumps(payload), headers=headers) as r:
            if not r.status > 299:
                logging.info("Posted server count to DBL. ({} shards/{} guilds)".format(bot.shard_count, len(bot.guilds)))
            else:
                logging.error("Error posting stats to DBL.")
                logging.error("HTTP " + str(r.status))
                logging.error(str(await r.json()))
        headers = {
            "Authorization": settings.BotList.BOTSDISCORDPW,
            "Content-Type": "application/json"
        }
        async with session.post("https://bots.discord.pw/api/bots/375805687529209857/stats", data=json.dumps(payload), headers=headers) as r:
            if not r.status > 299:
                logging.info("Posted server count to bots.discord.pw. ({} shards/{} guilds)".format(bot.shard_count, len(bot.guilds)))
            else:
                logging.error("Error posting stats to bots.discord.pw.")
                logging.error("HTTP " + str(r.status))
                logging.error(str(await r.json()))
        payload = {
            "count": len(bot.guilds),
            "server_count": len(bot.guilds)
        }
        headers = {
            "Authorization": settings.BotList.BOTSFORDISCORD,
            "Content-Type": "application/json"
        }
        async with session.post("https://botsfordiscord.com/api/bot/375805687529209857", data=json.dumps(payload), headers=headers) as r:
            if not r.status > 299:
                logging.info("Posted server count to botsfordiscord.com. ({} shards/{} guilds)".format(bot.shard_count, len(bot.guilds)))
            else:
                logging.error("Error posting stats to botsfordiscord.com.")
                logging.error("HTTP " + str(r.status))
                logging.error(str(await r.json()))
        headers = {
            "Authorization": "Bot " + settings.BotList.DISCORDBOTLIST,
            "Content-Type": "application/json"
        }
        payload = {
            "guilds": len(bot.guilds),
            "users": len(list(bot.get_all_members()))
        }
        async with session.post("https://discordbotlist.com/api/bots/375805687529209857/stats", data=json.dumps(payload), headers=headers) as r:
            if not r.status > 299:
                logging.info("Posted server count to discordbotlist.com. ({} guilds/{} users)".format(len(bot.guilds), len(list(bot.get_all_members()))))
            else:
                logging.error("Error posting stats to discordbotlist.com.")
                logging.error("HTTP " + str(r.status))
                logging.error(str(await r.json()))
        #headers = {
        #    "Authorization": settings.BotList.KONOMIBOTS,
        #    "Content-Type": "application/json"
        #}
        #payload = {
        #    "guild_count": len(bot.guilds)
        #}
        #async with session.post("http://bots.disgd.pw/api/bot/375805687529209857/stats", data=json.dumps(payload), headers=headers) as r:
        #    if not r.status > 299:
        #        logging.info("Posted server count to konomi bots. ({} shards/{} guilds)".format(bot.shard_count, len(bot.guilds)))
        #    else:
        #        logging.error("Error posting stats to konomi bots.")
        #        logging.error("HTTP " + str(r.status))
        #        logging.error(str(await r.text()))

def send_help_content():
    e = discord.Embed(title="<:twitch:404633403603025921> **TwitchBot Help**", color=discord.Color(0x6441A4))
    e.add_field(name="Commands", value="TwitchBot responds to commands starting with `twitch` or `!twitch`. Type `twitch commands` to view all runnable commands.", inline=False)
    e.add_field(name="Support", value="If you need help with the bot, you can join the [support server](https://discordapp.com/invite/UNYzJqV) where our staff team will assist you.", inline=False)
    e.add_field(name="Website", value="You can view information about TwitchBot at https://twitchbot.io")
    e.add_field(name="TwitchBot Premium", value="Support TwitchBot's development and get a handful of cool features and benefits for just $5.00 USD a month. https://twitchbot.io/premium", inline=False)
    e.add_field(name="Upvote Competition", value="We're giving away TwitchBot Premium for FREE to the top three voters at the end of every month! [Upvote here](https://discordbots.org/bot/twitch/vote) and [view the leaderboard](http://dash.twitchbot.io/leaderboard)")
    e.add_field(name="About", value="TwitchBot was made by [Akira#4587](https://disgd.pw) using discord.py. To view other contributors, type `twitch info`.")
    e.add_field(name="Other links", value="[FAQ](https://twitchbot.io/faq) · [Dashboard](http://dash.twitchbot.io) · [Upvote](https://discordbots.org/bot/twitch/vote) · [Invite](https://discordapp.com/oauth2/authorize?client_id=375805687529209857&permissions=8&scope=bot&response_type=code&redirect_uri=https://twitchbot.io/?invited) · [Blog](https://medium.com/twitchbot)", inline=False)
    #e.add_field(name=":flag_us: :flag_gb: :flag_es: :flag_br: :flag_fr: :flag_jp:", value="""
    #Want to help translate TwitchBot to your language? We're hiring volunteer translators to make TwitchBot available in multiple languages!
    #
    #**Apply here if you're interested: https://twitchbot.io/translators**
    #    """)
    return e

def send_commands_content():
    e = discord.Embed(color=discord.Color(0x6441A4), title="<:twitch:404633403603025921> TwitchBot Commands")
    e.description = ":warning: __**Do not put `<>` or `[]` around command arguments.**__"
    e.add_field(name="General", value="""
`twitch help` - Shows bot help
`twitch info` - Shows bot info
`twitch invite` - Displays a link to add TwitchBot to your server
`twitch status` - Shows Twitch API status
`twitch ping` - Pong!
""", inline=False)
    e.add_field(name="Twitch", value="""
`twitch user <user>` - Gets info on a Twitch channel
`twitch stream user <user>` - Gets info on a user's stream
`twitch stream watch <user>` - Watch a Twitch stream from Discord
`twitch stream game <name>` - Watch someone stream the specified game
`twitch stream top` - Fetches info on a top stream
`twitch game <name>` - Gets info on a Twitch game
`twitch top` - Gets the most popular Twitch games
    """, inline=False)
    e.add_field(name="Clips", value="""
`twitch clips from <user>` - Gets a clip from the specified Twitch user
`twitch clips trending` - Gets a trending clip
`twitch clips game <game>` - Gets a clip from the specified game
`twitch clips uservoted` - Gets one of the most popular clips voted by TwitchBot users
    """, inline=False)
    e.add_field(name="Streamer Notifications", value="""
`twitch notif add [#discord_channel] [streamer_name] [message]` - Adds a streamer notification for a streamer to the specified channel
`twitch notif remove <#discord_channel> <streamer_name>` - Remove a streamer notification for a streamer to the specified channel
`twitch notif list [#discord_channel]` - Lists the streamer notifications for the specified channel
`twitch notif formatting` - Shows variables that you can insert into streamer notification messages
    """, inline=False)
    e.add_field(name="Live Role", value="""
`twitch live_role set` - Sets the Live Role for the current server
`twitch live_role delete` - Removes the Live Role configuration
`twitch live_role view` - Tells you which role is currently set up
    """, inline=False)
    e.add_field(name="Audio", value="""
`twitch listen <user>` - Listen to a Twitch stream in the current voice channel
`twitch nowplaying` - Shows the stream currently playing, if any
`twitch leave` - Leaves a voice channel
    """, inline=False)
    e.add_field(name="Game Stats", value="""
`twitch overwatch <pc/psn/xbl> <player>` - Shows Overwatch player stats
`twitch fortnite <pc/psn/xbl> <player>` - Shows Fortnite player stats
    """)
    e.add_field(name="Moderation", value="""
`twitch ban <@user> [reason]` - Bans a user with an optional reason
`twitch kick <@user> [reason]` - Kicks a user with an optional reason
`twitch purge <amt>` - Bulk-deletes the specified amount of messages from the current channel
`twitch filter set <sensitivity>` - Sets the server-wide toxicity filter
`twitch filter remove` - Removes the server-wide toxicity filter
    """, inline=False)
    return e

def create_guild_join_embed(bot, guild):
    bots = len(list(filter(lambda m: m.bot, guild.members)))
    usrs = len(guild.members) - bots
    e = discord.Embed(color=discord.Color.green())
    e.title = "Joined guild"
    e.description = "Now in {0} guilds with {1} users".format(len(bot.guilds), len(list(bot.get_all_members())))
    e.add_field(inline=False, name="Guild name", value="{0.name} (ID: {0.id})".format(guild))
    e.add_field(inline=False, name="Owner", value="{0} (ID: {0.id})".format(guild.owner))
    e.add_field(inline=False, name="Members", value="{0} users and {1} bots".format(usrs, bots))
    e.set_thumbnail(url=guild.icon_url)
    e.timestamp = datetime.datetime.now()
    return e

def create_guild_leave_embed(bot, guild):
    bots = len(list(filter(lambda m: m.bot, guild.members)))
    usrs = len(guild.members) - bots
    if guild.me:
        joined_at = guild.me.joined_at.timestamp()
        relative_join = time.gmtime(time.time() - joined_at)
        joined_at = time.gmtime(joined_at)
        join_txt = time.strftime("%a, %b %d at %I:%M %p", joined_at) + " - {0} years, {1} months, and {2} days ago".format(relative_join.tm_year - 1970, relative_join.tm_mon - 1, relative_join.tm_mday)
    else:
        join_txt = "Unknown"
    e = discord.Embed(color=discord.Color.red())
    e.title = "Left guild"
    e.description = "Now in {0} guilds with {1} users".format(len(bot.guilds), len(list(bot.get_all_members())))
    e.add_field(inline=False, name="Guild name", value="{0.name} (ID: {0.id})".format(guild))
    e.add_field(inline=False, name="Owner", value="{0} (ID: {0.id})".format(guild.owner))
    e.add_field(inline=False, name="Members", value="{0} users and {1} bots".format(usrs, bots))
    e.add_field(inline=False, name="Joined At", value=join_txt)
    e.set_thumbnail(url=guild.icon_url)
    e.timestamp = datetime.datetime.now()
    return e
