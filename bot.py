from discord.ext import commands
from utils import settings
import discord, asyncio
from utils.functions import TWAPI_REQUEST, STREAM_REQUEST, TRIGGER_WEBHOOK
from utils.exceptions import TooManyRequestsError
import dateutil.parser
from itertools import islice
from random import randint
import requests
import time, math
import json
import sys, os
import inspect
import logging, traceback

prefix = "twitch"
prefix_alt = "Twitch"
if settings.BETA:
    prefix = "twbeta"
    prefix_alt = "Twbeta"

bot = commands.AutoShardedBot(command_prefix=[prefix + " ", prefix_alt + " "])
loop = asyncio.get_event_loop()
modules = ["mod.general", "mod.users", "mod.games", "mod.streams", "mod.audio", "mod.notifs", "mod.stats", "mod.dev", "mod.clips"]

bot.notifs = json.loads(open(os.path.join(os.getcwd(), 'data', 'notifs.json')).read())
bot.cmds = 0
bot.ratelimits = {"twitch": 0, "fortnite": 0, "rocketleague": 0, "pubg": 0}
bot.vc = {}

logging.basicConfig(level=logging.INFO, format='%(levelname)s/%(module)s @ %(asctime)s: %(message)s', datefmt='%I:%M:%S %p')
log = logging.getLogger("bot.core")

log.info("Are we running as beta? {}".format(settings.BETA))

def post_stats():
    if not settings.BETA:
        r = requests.post("https://discordbots.org/api/bots/{}/stats".format(bot.user.id), headers={"Authorization": settings.BotList.DBL}, data={'server_count': len(bot.servers)})
        r.raise_for_status()

def split_every(n, iterable):
    i = iter(iterable)
    piece = list(islice(i, n))
    while piece:
        yield piece
        piece = list(islice(i, n))

async def change_presence():
    if not settings.BETA:
        await bot.change_presence(activity=discord.Game(name="twitch help • {} servers".format(len(bot.guilds)), type=1, url="https://twitch.tv/playoverwatch"))
    else:
        await bot.change_presence(activity=discord.Game(name="in development • twbeta help"), status=discord.Status.dnd)

for m in modules:
    try:
        bot.load_extension(m)
    except:
        log.error(traceback.format_exc())
    else:
        log.info("Successfully loaded " + m)

###########################
#                BOT EVENTS
###########################

@bot.event
async def on_ready():
    log.info("ready")
    bot.uptime = time.time()
    bot.cmds = 0
    await change_presence()
    post_stats()

@bot.event
async def on_error(event, *args, **kwargs):
    TRIGGER_WEBHOOK("Error in {}: {}".format(event, traceback.format_exc()))

@bot.event
async def on_command(command, ctx):
    bot.cmds += 1

@bot.event
async def on_server_join(server):
    await change_presence()
    log.info("Joined guild {0.name} / {0.id}".format(server))
    post_stats()

@bot.event
async def on_server_leave(server):
    await change_presence()
    log.info("Left guild {0.name} / {0.id}".format(server))
    post_stats()

@bot.event
async def on_command_error(error, ctx):
    if ctx.message.content.lower().startswith(prefix + " notif "):
        if isinstance(error, discord.NotFound):
            await ctx.send("That Discord text channel couldn't be found. Usage: `twitch notif add #discord_channel twitch_user`\nExample: `twitch notif add #general ninja`")
        else:
            await ctx.send("The correct usage is: `twitch notif add #discord_channel twitch_user`.\nExample: `twitch notif add #general ninja`")
        return
    elif ctx.message.content.lower().startswith(prefix + " listen"):
        if isinstance(error, discord.InvalidArgument):
            await ctx.send("You need to be in a valid voice channel.")
        return
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, discord.Forbidden):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You're missing required argument(s)!")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can't be used in private messages!")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to run this command.")
    elif isinstance(error, commands.DisabledCommand):
        await ctx.send("This command is disabled.")
    elif isinstance(error, TooManyRequestsError):
        await ctx.send("<:twitch:404633403603025921> Ratelimited by the Twitch API.")
        TRIGGER_WEBHOOK("Ratelimited by Twitch API! Command: `{}` (context: `{}`)".format(ctx.command.name, ctx.message.content))
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send("You can run this command in {} seconds.".format(round(error.retry_after, 1)))
    elif isinstance(error, requests.exceptions.RequestException):
        e = discord.Embed(color=discord.Color.red(), title="Web Request Failed", description="```{}```".format(error))
        await ctx.send(ctx.message.channel, embed=e)
        TRIGGER_WEBHOOK("{0.method} {0.url} {0.status_code} (command: {1.command})".format(error.request, ctx))
    else:
        log.error(str(error))
        e = discord.Embed(color=discord.Color.red(), title="An Error Occurred", description="```{}```".format(error))
        e.set_footer(text="Join the support server at discord.me/konomi")
        await ctx.send(embed=e)
        TRIGGER_WEBHOOK("Error in `{}`: {} (context: `{}`)".format(ctx.command.name, error, ctx.message.content))

###########################
#          PROCESS MESSAGES
###########################

@bot.event
async def on_command(ctx, command):
    bot.cmds += 1

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content.startswith(prefix) or message.content.startswith(prefix_alt):
        log.info("{0.author} #{0.channel} {0.server}: {0.content}".format(message))
        if message.content.lower() == prefix + " help":
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
            e.add_field(name="`Streamer Notifications`", value="""
`twitch notif add <#discord_channel> <twitch_username>` - Adds a streamer notification for a streamer to the specified channel
`twitch notif remove <#discord_channel> <twitch_username>` - Remove a streamer notification for a streamer to the specified channel
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
            e.add_field(name="`Links`", value="Discord Server: [discord.me/konomi](https://discord.me/konomi)\nWebsite: [twitch.disgd.pw](https://twitch.disgd.pw)\n**Upvote TwitchBot:** [discordbots.org](https://discordbots.org/bot/375805687529209857/vote)")
            e.set_footer(text="""
TwitchBot is not affiliated or endorsed by Discord, Inc. or Twitch Interactive, Inc.
            """)
            await ctx.send(embed=e)
        else:
            await bot.process_commands(message)
    elif message.content in ["<@{}>".format(bot.user.id), "twitch"]:
       ctx.send("Hello! <:twitch:404633403603025921> I'm TwitchBot. You can view my commands by typing `{} help`.".format(prefix))

@bot.command(hidden=True, name="reload")
async def _reload(ctx, cog):
    if not ctx.message.author.id == "236251438685093889": return
    try:
        bot.unload_extension(cog)
        bot.load_extension(cog)
    except Exception as e:
        await ctx.send("Failed to reload cog: `{}`".format(e))
    else:
        await ctx.send("Successfully reloaded cog.")

@bot.command(hidden=True, name="eval")
async def _eval(ctx, *, code):
    if not ctx.message.author.id == "236251438685093889": return
    try:
        e = eval(code)
        await ctx.send("```py\n{}\n```".format(e))
    except Exception as e:
        await ctx.send("```py\n{}: {}\n```".format(type(e).__name__, e))

###########################
#          BACKGROUND TASKS
###########################

async def poll_twitch():
    if not False:
        await bot.wait_until_ready()
        while not bot.is_closed:
            log.info("Polling Twitch for {} live users".format(len(bot.notifs)))
            notifs_to_send = split_every(100, dict(bot.notifs)) # Copy so we don't get "dictionary changed size during iteration"
            for nts in notifs_to_send:
                query_params = "?first=100&user_id=" + ("&user_id=".join(nts))
                try:
                    r = await STREAM_REQUEST(bot, "/streams" + query_params)
                    streams = {}
                    data = r.json()['data']
                    for d in data:
                        r = ""
                        try:
                            r = await STREAM_REQUEST(bot, "/users?id=" + d['user_id'])
                        except:
                            r = TWAPI_REQUEST("https://api.twitch.tv/helix/users?id=" + d['user_id'])
                        streams[d['user_id']] = {"stream": d, "user": r.json()['data'][0]} # Get only live users
                    for s in streams.keys():
                        stream = streams[s]['stream']
                        user = streams[s]['user']
                        e = discord.Embed(color=0x6441A4)
                        e.set_author(icon_url=user['profile_image_url'], name=user['login'] + " is now live!", url="https://twitch.tv/" + user['login'])
                        e.set_thumbnail(url=user['profile_image_url'])
                        e.title = "Streaming " + stream['title']
                        e.description = " **[Watch on Twitch](https://twitch.tv/{})**".format(user['login'])
                        for c in bot.notifs[s]:
                            if not bot.notifs[s][c] == stream['id']:
                                try:
                                    chan = bot.get_channel(c)
                                    if c in [442389961895968768, 423497606682116106]:
                                        await chan.send("@everyone", embed=e)
                                    else:
                                        await chan.send(embed=e)
                                except discord.InvalidArgument:
                                    del bot.notifs[s][c]
                                except:
                                    log.error(traceback.format_exc())
                                bot.notifs[s][c] = stream['id']
                        await asyncio.sleep(1)
                    await asyncio.sleep(1)
                except TooManyRequestsError:
                    TRIGGER_WEBHOOK("Ratelimited by Twitch API! (command: poll_twitch)")
            await asyncio.sleep(240)

###########################
#                   RUN BOT
###########################

try:
    bot.loop.create_task(poll_twitch())
    if settings.BETA:
        bot.run(settings.BETA_TOKEN)
    else:
        bot.run(settings.TOKEN)
except KeyboardInterrupt:
    f = open(os.path.join(os.getcwd(), 'data', 'notifs.json'), 'w')
    f.write(json.dumps(bot.notifs))
    f.close()
    loop.run_until_complete(bot.logout())
except:
    log.fatal(traceback.format_exc())
