import discord
import traceback, logging
from discord.ext import commands
from collections import Counter
from utils import settings, lang, http, functions, paginator
from copy import copy
import json, re
import os, os.path
import aiohttp, asyncio
import logging, traceback
import typing, textwrap
import datadog
import secrets
import time, dateutil.parser, datetime
import requests
import rethinkdb as r
r = r.RethinkDB()

log = logging.getLogger("bot.live")

class LiveRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("bot.live_role")
        bot.loop.create_task(self.update_cache())
        bot.loop.create_task(self.check_roles())

    def __cache_pull__(self):
        self.bot.live_role = list(r.table('live_role').run(self.bot.rethink, durability="soft"))

    async def update_cache(self):
        __nonce__ = secrets.token_urlsafe(5)
        self.__cache_nonce__ = __nonce__
        while not self.bot.is_closed():
            if not self.__cache_nonce__ == __nonce__:
                self.logger.info('Preventing duplicate cache update run')
                return
            self.logger.info(f'Updating live role cache {__nonce__}')
            self.__cache_pull__()
            await asyncio.sleep(30)

    async def check_roles(self):
        await self.bot.wait_until_ready()
        if not hasattr(self.bot, 'live_role'):
            self.logger.info('Live role status not pulled from database; forcing pull')
            self.__cache_pull__()
        guild_ids = map(lambda g: str(g.id), self.bot.guilds)
        live_role = filter(lambda g: (g['id'] in guild_ids) and (g.get('role') is not None), self.bot.live_role)
        self.logger.info(f"Updating live role status of {len(list(live_role))} guilds")
        count = 0
        for guild in live_role:
            ctx = self.bot.get_guild(int(guild['id']))
            role = ctx.get_role(int(guilds['role']))
            frole = ctx.get_role(int(guilds.get('filter', 0)))
            if ctx is None or role is None:
                continue # either the guild or live role doesn't exist
            to_remove = filter(lambda m: (role.id in map(lambda r: r.id, m.roles)) and (not isinstance(m.activity, discord.Streaming)), ctx.members)
            for member in to_remove:
                try:
                    await member.remove_roles(role, reason="Member finished streaming on Twitch")
                    count += 1
                    self.logger.debug(f'Removed live role from {member.id} in {member.guild.id}')
                except discord.Forbidden:
                    pass
                except:
                    self.logger.error(f"Failed to remove live role:\n{traceback.format_exc()}")
            to_add = filter(lambda m: (role.id not in map(lambda r: r.id, m.roles)) and isinstance(m.activity, discord.Streaming), ctx.members)
            if frole is not None:
                to_add = filter(lambda m: frole.id in map(lambda r: r.id, m.roles), to_add)
            for member in to_add:
                try:
                    await member.add_roles(role, reason="Member started streaming on Twitch")
                    count += 1
                    self.logger.debug(f'Added live role to {member.id} in {member.guild.id}')
                except discord.Forbidden:
                    pass
                except:
                    self.logger.error(f"Failed to add live role:\n{traceback.format_exc()}")
        self.logger.info(f"Updated the live role status of {count} members")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.guild is None or before.bot:
            return
        elif not hasattr(self.bot, 'live_role'):
            self.logger.info('Live role status not pulled from database; forcing pull')
            self.__cache_pull__()
        was_streaming = isinstance(before.activity, discord.Streaming)
        is_streaming = isinstance(after.activity, discord.Streaming)
        self.logger.debug(f"member update {after.guild.id} {after.id}: {was_streaming} -> {is_streaming}")
        if was_streaming == is_streaming: return
        await self.bot.wait_until_ready()
        lr_info = discord.utils.find(lambda r: r['id'] == str(after.guild.id), self.bot.live_role)
        if lr_info is None: return
        elif not lr_info.get('role'): return
        self.logger.debug(str(lr_info))
        role = discord.Object(id=int(lr_info['role']))
        frole = discord.Object(id=int(lr_info.get('filter', 0)))
        try:
            if (not was_streaming) and is_streaming: # user just went live
                if frole.id != 0 and discord.utils.get(after.roles, id=frole.id) is None:
                    self.logger.debug(f'Not adding role to {after.id} in {after.guild.id}; they don\'t have the filter role')
                    return # user doesn't have filter role
                await after.add_roles(role, reason="Member started streaming on Twitch")
                self.logger.debug(f'Added live role to {after.id} in {after.guild.id}')
            elif was_streaming and (not is_streaming): # user isn't live anymore
                if discord.utils.get(after.roles, id=role.id) is None:
                    self.logger.debug(f'Not removing role from {after.id} in {after.guild.id}; they don\'t have the live role')
                    return # user doesn't have the live role, so don't bother continuing
                await after.remove_roles(role, reason="Member finished streaming on Twitch")
                self.logger.debug(f'Removed live role for {after.id} in {after.guild.id}')
        except discord.Forbidden:
            self.logger.debug(f"Live role forbidden for {after.id} in {after.guild.id}")
        except TypeError as e:
            self.logger.warn(f"live role TypeError: {e}")
        except Exception:
            raise

    @commands.group(no_pm=True, aliases=['live_check', 'lc', 'lr'])
    async def live_role(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(embed=lang.EmbedBuilder(msgs['live_role']['command_usage']))

    @live_role.command()
    async def set(self, ctx, *, role: typing.Union[discord.Role, str] = None):
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        elif not ctx.guild.me.permissions_in(ctx.channel).manage_roles:
            return await ctx.send(msgs['permissions']['bot_need_perm'].format(permission="Manage Roles"))
        if role is None:
            return await ctx.send(msgs['live_role']['no_role_mentioned'])
        if type(role) == str:
            role = discord.utils.find(lambda m: role.lower() in m.name.lower(), ctx.guild.roles)
            if role is None:
                return await ctx.send(msgs['live_role']['role_not_found'])
        r.table('live_role').insert({"id": str(ctx.guild.id), "role": str(role.id)}, conflict="update").run(self.bot.rethink, durability="soft", noreply=True)
        await ctx.send(msgs['live_role']['add_success'].format(role=role.name))
        cursor = r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink, durability="soft")
        if cursor is None:
            return # db hasn't updated yet
        g = ctx.guild
        try:
            filt = cursor.get('filter')
            lc = int(cursor['role'])
            role = discord.utils.find(lambda r: r.id == int(lc), g.roles)
            for m in filter(lambda m: isinstance(m.activity, discord.Streaming), g.members):
                if not m.bot:
                    if filt is not None:
                        frole = discord.utils.get(g.roles, id=int(filt))
                        if not frole.id in map(lambda r: r.id, m.roles):
                            continue
                    log.info("Adding streamer role to {before.id} in {before.guild.id}".format(before=m))
                    await m.add_roles(role, reason="User went live on Twitch")
        except discord.Forbidden as e:
            await ctx.send(msgs['live_role']['missing_perms_ext'])

    @live_role.command(name="filter", no_pm=True)
    async def _filter(self, ctx, *, role: typing.Union[discord.Role, str] = None):
        """Restricts Live Role to users with a specific role"""
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        elif not ctx.guild.me.permissions_in(ctx.channel).manage_roles:
            return await ctx.send(msgs['permissions']['bot_need_perm'].format(permission="Manage Roles"))
        if role is None:
            return await ctx.send(msgs['live_role']['no_role_mentioned'])
        if type(role) == str:
            role = discord.utils.find(lambda m: role.lower() in m.name.lower(), ctx.guild.roles)
            if role is None:
                return await ctx.send(msgs['live_role']['role_not_found'])
        cursor = r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink, durability="soft")
        if cursor is None:
            return await ctx.send(msgs['live_role']['not_set_up'])
        r.table('live_role').insert({"id": str(ctx.guild.id), "filter": str(role.id)}, conflict="update").run(self.bot.rethink, durability="soft", noreply=True)
        await ctx.send(msgs['live_role']['filter_success'])
        g = ctx.guild
        filt = role.id
        lc = int(cursor['role'])
        role = discord.utils.find(lambda r: str(r.id) == str(lc), g.roles)
        for m in filter(lambda m: role.id in map(lambda r: r.id, m.roles), g.members):
            if filt is not None:
                frole = discord.utils.get(g.roles, id=int(filt))
                if not frole.id in map(lambda r: r.id, m.roles):
                    log.info("Removing streamer role from {before.id} in {before.guild.id}".format(before=m))
                    await m.remove_roles(role, reason="User does not have filter role for Live Role")

    @live_role.command(aliases=['del', 'remove'])
    async def delete(self, ctx):
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        try:
            cursor = r.table('live_role').get(str(ctx.guild.id))
            if cursor.run(self.bot.rethink, durability="soft") is None:
                return await ctx.send(msgs['live_role']['not_set_up'])
            cursor.delete().run(self.bot.rethink, durability="soft", noreply=True)
        except KeyError as e:
            return await ctx.send(msgs['live_role']['not_set_up'])
        except:
            raise
        else:
            return await ctx.send(msgs['live_role']['del_success'])

    @live_role.command(aliases=['list'])
    async def view(self, ctx):
        msgs = await lang.get_lang(ctx)
        cursor = r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink, durability="soft")
        if cursor is None:
            return await ctx.send(msgs['live_role']['not_set_up'])
        role = discord.utils.find(lambda n: n.id == int(cursor['role']), ctx.guild.roles)
        await ctx.send(msgs['live_role']['view_response'].format(role=role.name))

    @live_role.command()
    async def check(self, ctx):
        try:
            msgs = await lang.get_lang(ctx)
            cursor = r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink, durability="soft")
            if cursor is None:
                return await ctx.send(msgs['live_role']['not_set_up'])
            try:
                role = ctx.guild.get_role(int(cursor['role']))
                if cursor.get('filter') is not None:
                    cursor['filter'] = ctx.guild.get_role(int(cursor['filter']))
            except TypeError:
                return await ctx.send(msgs['live_role']['not_set_up'])
            e = discord.Embed(color=0x6441A4, title="Live Role Check")
            live_members = len(list(filter(lambda m: isinstance(m.activity, discord.Streaming) and not m.bot, ctx.guild.members)))
            members_with_lr = len(list(filter(lambda m: role in m.roles, ctx.guild.members)))
            status = "<:tickYes:342738345673228290>"
            if live_members != members_with_lr:
                status = "<:tickNo:342738745092734976>"
            e.description = textwrap.dedent(f"""\
            Live role: {role.name}
            Filter: {str(cursor.get('filter'))}

            {live_members} members in server that are streaming
            {members_with_lr} members with the server's live role

            **Live role status: {status}**
            """)
            e.set_footer(text="Note: This command will not work properly if a filter role has been set")
            await ctx.send(embed=e)
        except:
            await ctx.send(traceback.format_exc())

class Notifs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile('^\w+$')

    @commands.group(no_pm=True)
    async def notif(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(embed=lang.EmbedBuilder(msgs['notifs']['command_usage']))

    @notif.command(no_pm=True)
    async def add(self, ctx, discord_channel: discord.TextChannel = None, twitch_user: str = None, *, msg: str = None):
        """Sets up notifications for a Twitch user in the specified channel."""
        msgs = await lang.get_lang(ctx)
        try:
            if not ctx.guild:
                return await ctx.send(msgs['permissions']['no_pm'])
            if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
                return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
            await ctx.send("**Notice:** The preferred method for adding notifications is now through the dashboard. We recommend that you use <https://dash.twitchbot.io> for a better experience.")
            prem_check = requests.get(f"https://api.twitchbot.io/premium/{ctx.author.id}", headers={"X-Auth-Key": settings.DashboardKey})
            if prem_check.json().get('premium') != True or prem_check.status_code != 200:
                channels = list(map(lambda c: str(c.id), ctx.guild.channels))
                serv_notifs = r.table('notifications').filter(lambda obj: r.expr(channels).contains(obj['channel'])).count().run(self.bot.rethink, durability="soft")
                if serv_notifs > 25:
                    return await ctx.send(msgs['notifs']['limit_reached'])
            s = None
            username = None
            if discord_channel is None:
                await ctx.send(msgs['notifs']['prompt1'])
                try:
                    m = await self.bot.wait_for('message', check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id, timeout=60)
                    discord_channel = discord.utils.find(lambda c: c.name.lower().startswith(m.clean_content.strip("#").lower()), ctx.guild.text_channels)
                    if discord_channel is None:
                        return await ctx.send(msgs['notifs']['text_channel_not_found'])
                except asyncio.TimeoutError:
                    return await ctx.send(msgs['notifs']['response_timeout'])
            perms = discord_channel.permissions_for(ctx.guild.me)
            check_val = functions.CheckMultiplePerms(perms, "read_messages", "send_messages", "embed_links", "external_emojis")
            if check_val != True:
                return await ctx.send(msgs['permissions']['bot_need_perm'].format(permission=check_val))
            if twitch_user == None:
                await ctx.send(msgs['notifs']['prompt2'])
                try:
                    m = await self.bot.wait_for('message', check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id, timeout=60)
                    username = m.content.split('/')[-1]
                    s = http.TwitchAPIRequest("https://api.twitch.tv/helix/users?login=" + username)
                    if s.status_code == 404:
                        return await ctx.send(msgs['notifs']['twitch_user_not_found'])
                    elif "data" not in s.json().keys():
                        return await ctx.send(f"{msgs['games']['generic_error']} {s.status_code}")
                    elif len(s.json().get('data', {})) == 0:
                        return await ctx.send(msgs['notifs']['twitch_user_not_found'])
                    elif s.status_code > 399:
                        return await ctx.send(f"{msgs['games']['generic_error']} {s.status_code}")
                except asyncio.TimeoutError:
                    return await ctx.send(msgs['notifs']['response_timeout'])
            else:
                username = twitch_user.split('/')[-1]
                s = http.TwitchAPIRequest("https://api.twitch.tv/helix/users?login=" + username)
                if s.status_code == 404 or len(s.json().get('data', {})) == 0:
                    return await ctx.send(msgs['notifs']['twitch_user_not_found'])
            try:
                s = s.json()['data'][0]
            except KeyError as e:
                return await ctx.send(f"{msgs['notifs']['invalid_data']} KeyError: f{str(e)}")
            except IndexError as e:
                return await ctx.send(f"{msgs['notifs']['invalid_data']} IndexError: f{str(e)}")
            if self.regex.match(username) is None:
                return await ctx.send(msgs['notifs']['malformed_user'])
            if msg == None:
                await ctx.send(msgs['notifs']['prompt3'])
                try:
                    m = await self.bot.wait_for('message', check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id, timeout=180)
                    if m.content.lower() == 'default' or m.content.lower() == '`default`':
                        msg = msgs['notifs']['default_msg'].format(channel=username)
                    else:
                        msg = m.content
                except asyncio.TimeoutError:
                    return await ctx.send(msgs['notifs']['response_timeout'])
            try:
                object = {"channel": str(discord_channel.id), "streamer": s['id'], "name": username, "last_stream_id": None, "message": msg}
                existing_notif = r.table('notifications').filter((r.row['streamer'] == s['id']) & (r.row['channel'] == str(discord_channel.id)))
                if existing_notif.count().run(self.bot.rethink, durability="soft") == 0:
                    r.table('notifications').insert(object).run(self.bot.rethink, durability="soft", noreply=True)
                else:
                    existing_notif.update(object).run(self.bot.rethink, durability="soft")
                return await ctx.send(msgs['notifs']['add_success'].format(user=username, channel=discord_channel.mention))
            except KeyError as e:
                return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])
            except IndexError as e:
                return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])
            except:
                raise
        except:
            await ctx.send(traceback.format_exc())

    @notif.command(no_pm=True)
    async def list2(self, ctx, channel: discord.TextChannel = None):
        """Lists notifications in the current channel."""
        msgs = await lang.get_lang(ctx)
        if not ctx.guild:
            return await ctx.send(msgs['permissions']['no_pm'])
        channel = channel or ctx.channel
        notifs = list(r.table('notifications').filter(r.row['channel'].eq(str(channel.id))).run(self.bot.rethink, durability="soft"))
        if len(notifs) == 0:
            return await ctx.send(msgs['notifs']['no_notifs'])
        e = discord.Embed(color=0x6441A4, title=f"Notifications for #{ctx.channel.name}", description=f"Notification count: {len(notifs)}\n[View on Dashboard](https://dash.twitchbot.io/servers/{ctx.guild.id})")
        for notif in notifs:
            e.add_field(name=notif.get('name', notif['streamer']), value=notif['message'])
        pager = paginator.EmbedPaginator(e)
        await pager.page(ctx)

    @notif.command(no_pm=True)
    async def list(self, ctx, channel: discord.TextChannel = None):
        """Lists notifications in the current channel."""
        msgs = await lang.get_lang(ctx)
        if not ctx.guild:
            return await ctx.send(msgs['permissions']['no_pm'])
        if channel is None:
            channel = ctx.channel
        f = list(r.table('notifications').filter(r.row['channel'].eq(str(channel.id))).run(self.bot.rethink, durability="soft"))
        e = discord.Embed(color=discord.Color(0x6441A4), title=msgs['notifs']['list_title'].format(channel=channel.name), description="There are {} streamer notifications set up for {}".format(len(f), channel.mention))
        msg = ""
        for notif in list(f):
            msg += f"**{notif.get('name', notif['streamer'])}** - {notif['message']}\n"
        if len(msg) > 1024:
            msg = ""
            e.description += f"\n{msgs['notifs']['list_embed_limit']}"
            for notif in f:
                msg += f"{notif.get('name', notif['streamer'])}\n"
        e.add_field(name=msgs['notifs']['notifications'], value=msg[:1024] or msgs['notifs']['no_notifs'])
        e.set_footer(icon_url=ctx.guild.icon_url, text=ctx.guild.name)
        await ctx.send(embed=e)

    @notif.command(aliases=["del", "delete"], no_pm=True)
    async def remove(self, ctx, discord_channel: discord.TextChannel, twitch_user: str = None, *, flags=""):
        """Deletes notifications for a Twitch user in the specified channel."""
        msgs = await lang.get_lang(ctx)
        flags = flags.split(" ")
        if not ctx.guild:
            return await ctx.send(msgs['permissions']['no_pm'])
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        if twitch_user == None:
            notifs = r.table('notifications').filter(r.row['channel'].eq(str(discord_channel.id)))
            cnt = notifs.count().run(self.bot.rethink, durability="soft")
            await ctx.send(f":warning: {msgs['notifs']['bulk_delete_confirm']}".format(count=cnt, channel=discord_channel.mention))
            try:
                m = await self.bot.wait_for('message', check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id, timeout=60)
                if not "yes" in m.clean_content.lower():
                    return await ctx.send(msgs['notifs']['command_cancelled'])
                notifs.delete().run(self.bot.rethink, durability="soft", noreply=True)
                return await ctx.send(msgs['notifs']['bulk_delete_success'].format(count=cnt, channel=discord_channel.mention))
            except asyncio.TimeoutError:
                return await ctx.send(msgs['notifs']['response_timeout'])
        else:
            username = twitch_user.split('/')[-1]
            if self.regex.match(username) is None:
                return await ctx.send(msgs['notifs']['malformed_user'])
            try:
                if not "--force-user-id" in flags:
                    s = http.TwitchAPIRequest("https://api.twitch.tv/helix/users?login=" + username)
                    if s.status_code == 404:
                        return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])
                    s = s.json()
                else:
                    s = {"data": [{"id": twitch_user}]}
                r.table('notifications').filter((r.row['streamer'] == s['data'][0]['id']) & (r.row['channel'] == str(discord_channel.id))).delete().run(self.bot.rethink, durability="soft", noreply=True)
            except KeyError:
                await ctx.send(msgs['notifs']['del_fail'])
            except IndexError:
                await ctx.send(msgs['notifs']['del_fail'])
            except:
                await ctx.send(traceback.format_exc())
            else:
                await ctx.send(msgs['notifs']['del_success'].format(channel=discord_channel.mention, user=username))

    @notif.command()
    async def preview(self, ctx, discord_channel: discord.TextChannel, twitch_user: str):
        """Sends a preview for a notification."""
        msgs = await lang.get_lang(ctx)
        username = twitch_user.split('/')[-1]
        if self.regex.match(username) is None:
            return await ctx.send(msgs['notifs']['malformed_user'])
        await ctx.trigger_typing()
        req = http.TwitchAPIRequest(f"https://api.twitch.tv/helix/users?login={username}")
        if req.status_code == 404 or len(req.json().get('data', [])) < 1:
            return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])
        elif req.status_code != 200:
            return await ctx.send(f"{msgs['notifs']['invalid_data']} {req.status_code}")
        req = req.json()['data'][0]
        notif = r.table('notifications').filter((r.row['streamer'] == req['id']) & (r.row['channel'] == str(discord_channel.id)))
        if notif.count().run(self.bot.rethink, durability="soft") == 0:
            return await ctx.send(msgs['notifs']['del_fail'])
        notif = list(notif.run(self.bot.rethink, durability="soft"))[0]
        e = discord.Embed(color=discord.Color(0x6441A4))
        e.title = "**Stream Title**"
        e.description = f"\nPlaying Game for 123 viewers\n[Watch Stream](https://twitch.tv/{req['login']})"
        e.timestamp = datetime.datetime.now()
        e.url = "https://twitch.tv/" + req['login']
        e.set_footer(text="Notification preview")
        author_info = {
            "name": "{} is now live on Twitch!".format(req['display_name']),
            "url": e.url,
            "icon_url": req['profile_image_url']
        }
        e.set_author(**author_info)
        e.set_image(url="https://images-ext-1.discordapp.net/external/FueXlfSkrjOeYMx92Qe3Y2AaV4G5dk9ijVlNGpF-AgU/https/static-cdn.jtvnw.net/previews-ttv/live_user_overwatchcontenders-1920x1080.jpg")
        fmt_vars = {
            "$title$": "Stream Title",
            "$viewers$": "123",
            "$game$": "Game",
            "$url$": "https://twitch.tv/{}".format(req['login']),
            "$name$": req['display_name'],
            "$everyone$": "@everyone",
            "$here$": "@here"
        }
        msg = functions.ReplaceAllInStr(notif['message'], fmt_vars)
        msg = functions.ReplaceAllInStr(msg, {"@everyone": "@\u200beveryone", "@here": "@\u200bhere"})
        return await ctx.send(msg, embed=e)

    @notif.command()
    async def formatting(self, ctx):
        msgs = await lang.get_lang(ctx)
        e = lang.EmbedBuilder(msgs['notifs']['notif_variables'])
        e.set_footer(icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url, text=str(ctx.author))
        await ctx.send(embed=e)


async def poll4(bot):
    logging.info('[notifs] waiting for READY event...')
    await bot.wait_until_ready()
    _nonce = secrets.token_urlsafe(5)
    bot._notification_nonce = _nonce
    while not bot.is_closed():
        if not bot._notification_nonce == _nonce:
            logging.info('preventing duplicate notif run')
            return
        if not hasattr(bot, 'aiohttp'):
            bot.aiohttp = aiohttp.ClientSession()
        try:
            bot.last_notif_run = time.time()
            msgs_sent = 0
            logging.info('[notifs] looping notification list...')
            channels = bot.get_all_channels()
            streamers = list(r.table('notifications').filter(
                lambda n: (n['channel'] in channels)# & (n.get('webhook') != True)
            ).run(bot.rethink, durability="soft"))
            cnt = Counter(map(lambda n: n['streamer'], streamers))
            splits = functions.SplitIterable(100, cnt)
            for split in splits: # go over each split of 100
                users = split.keys()
                if len(users) == 0:
                    logging.info('[notifs] empty page')
                    continue
                stream_data = (await http.AsyncTwitchAPIStreamRequest(bot, f"/streams?user_id={'&user_id='.join(users)}"))['data']
                if len(stream_data) == 0:
                    logging.info('[notifs] no live users in this page')
                    continue
                users = list(map(lambda s: s['user_id'], stream_data)) # filter to live users
                games = list(Counter(map(lambda s: s['game_id'], stream_data)).keys()) # map games
                user_data = (await http.AsyncTwitchAPIStreamRequest(bot, f"/users?id={'&id='.join(users)}"))['data']
                game_data = (await http.AsyncTwitchAPIStreamRequest(bot, f"/games?id={'&id='.join(games)}"))['data']
                for stream in stream_data:
                    user = list(filter(lambda u: u['id'] == stream['user_id'], user_data))
                    game = list(filter(lambda g: g['id'] == stream['game_id'], game_data))
                    if len(user) == 0:
                        continue # user isn't live
                    else: user = user[0]
                    if len(game) == 0: game = {"id": 0, "name": "Unknown"}
                    else: game = game[0]
                    e = discord.Embed(color=discord.Color(0x6441A4))
                    e.title = f"**{stream['title']}**"
                    e.url = f"https://twitch.tv/{user['login']}"
                    e.description = f"Playing {game['name']} for {stream['viewer_count']} viewers\n[Watch Stream]({e.url})"
                    e.timestamp = dateutil.parser.parse(stream['started_at'])
                    author_info = {
                        "name": f"{user['display_name']} is now live on Twitch!",
                        "url": e.url,
                        "icon_url": user['profile_image_url']
                    }
                    e.set_author(**author_info)
                    e.set_image(url=f"{stream['thumbnail_url'].format(width=1920, height=1080)}?{secrets.token_urlsafe(5)}")
                    e.set_footer(text="twitchbot.io")
                    fmt_vars = {
                        "$title$": stream['title'].replace("_", "\\_"),
                        "$viewers$": stream['viewer_count'],
                        "$game$": game['name'].replace("_", "\\_"),
                        "$url$": f"https://twitch.tv/{user['login']}".replace("_", "\\_"),
                        "$name$": user['display_name'].replace("_", "\\_"),
                        "$everyone$": "@everyone",
                        "$here$": "@here"
                    }
                    notifs = list(filter(lambda n: n['streamer'] == user['id'], streamers))
                    for notif in notifs: # all notifs for that streamer
                        if notif['last_stream_id'] == stream['id']: continue # already notified for this stream
                        embed = copy(e) # copy for individual custom options
                        # --- Begin beta features --- #
                        if notif.get('prevent_doubling'):
                            # check if a notification was sent in the last hour
                            if float(notif.get('last_post', 0)) + 3600*8 >= time.time():
                                r.table('notifications').get(notif['id']).update({'last_stream_id': stream['id']}).run(bot.rethink, durability="soft", noreply=True)
                                continue
                        if notif.get('minimal_embed'):
                            embed.set_image(url="")
                        if notif.get('remove_embed'):
                            embed = None
                        try:
                            # Custom embed color
                            embed.color = int("0x" + notif.get('embed_color', "6441A4"), 16)
                        except:
                            pass
                        # --- End beta features --- #
                        channel = bot.get_channel(int(notif['channel']))
                        if channel is None:
                            #logging.info(f"[notifs] channel id {notif['channel']} does not exist")
                            #r.table('notifications').get(notif['id']).delete().run(bot.rethink, durability="soft", noreply=True)
                            continue
                        msg = functions.ReplaceAllInStr(notif['message'], fmt_vars)
                        try:
                            await channel.send(msg, embed=embed)
                            msgs_sent += 1
                            logging.info(f"[notifs] sent notificiation for {notif['streamer']} in {notif['channel']}")
                            r.table('notifications').get(notif['id']).update({'last_stream_id': stream['id'], 'last_post': str(time.time())}).run(bot.rethink, durability="soft", noreply=True)
                            await asyncio.sleep(0.5)
                        except discord.Forbidden:
                            r.table('notifications').get(notif['id']).delete().run(bot.rethink, durability="soft", noreply=True)
                            logging.info(f"[notifs] forbidden for channel {notif['channel']}")
                            continue
                await asyncio.sleep(0.5)
            logging.info(f"[notifs] looped {len(streamers)} notifs in {time.time() - bot.last_notif_run}s and sent {msgs_sent} messages")
            if not settings.UseBetaBot:
                datadog.statsd.histogram('bot.notif_runtime', time.time() - bot.last_notif_run)
                await http.SendMetricsWebhook(f"Processed {len(streamers)} notifs in {time.time() - bot.last_notif_run}s and sent {msgs_sent} messages")
        except Exception as e:
            logging.error(f"Error {type(e).__name__} in notification loop:\n{traceback.format_exc()}")
            if not settings.UseBetaBot:
                datadog.api.Event.create(title="Notification error", text=traceback.format_exc(), alert_type="error")
        finally:
            await asyncio.sleep(60)


def setup(bot):
    bot.add_cog(LiveRole(bot))
    bot.add_cog(Notifs(bot))
    bot.loop.create_task(poll4(bot))
