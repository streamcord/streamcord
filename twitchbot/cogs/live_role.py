import asyncio
import discord
import json
import logging
import secrets
import time
import traceback
import typing

from discord.ext import commands
from os import getenv
from rethinkdb import RethinkDB
from ..utils import lang, functions

r = RethinkDB()
r.set_loop_type('asyncio')


class LiveRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("bot.live_role")
        self.activity_predicate = lambda a: isinstance(a, discord.Streaming)
        self.streaming_predicate = lambda m: not (m.bot or discord.utils.find(self.activity_predicate, m.activities) is None)

        bot.loop.create_task(self.cache_update_loop())

    async def _pull_cache(self):
        ctime = time.time()
        cur = await r.table('live_role').run(self.bot.rethink)
        self.bot.live_role = [g async for g in cur]
        self.log.info('Updated live role cache in %ims', round((time.time() - ctime) * 1000))

    async def cache_update_loop(self):
        await self.bot.wait_until_ready()
        _nonce = secrets.token_urlsafe(5)
        self._cache_nonce = _nonce
        while not self.bot.is_closed():
            if self._cache_nonce != _nonce:
                return self.log.info('Preventing duplicate cache update loop')
            await self._pull_cache()
            await asyncio.sleep(60)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        try:
            if before.guild is None or before.bot:
                return
            before_activity = discord.utils.find(self.activity_predicate, before.activities)
            after_activity = discord.utils.find(self.activity_predicate, after.activities)
            was_streaming = before_activity is not None
            is_streaming = after_activity is not None
            if was_streaming == is_streaming:
                return

            await self.bot.wait_until_ready()
            is_event_backlogged = False
            while not hasattr(self.bot, 'live_role'):
                if 'live-role-backlog' in getenv('SC_DISABLED_FEATURES'):
                    return
                if not is_event_backlogged:
                    self.log.info('MEMBER_UPDATE event for %i is being backlogged', before.id)
                    is_event_backlogged = True
                await asyncio.sleep(0.1)
            if is_event_backlogged:
                self.log.info('Processing backlogged MEMBER_UPDATE event for %i', before.id)

            liverole = discord.utils.find(lambda r: r['id'] == str(after.guild.id), self.bot.live_role)
            if liverole is None or not liverole.get('role'):
                return
            self.log.debug(
                'MEMBER_UPDATE for %i in %i: streaming state changed from %s to %s',
                after.guild.id, after.id, was_streaming, is_streaming)

            role = after.guild.get_role(int(liverole['role']))
            if not role:
                return
            frole = liverole.get('filter')
            frole = after.guild.get_role(int(frole)) if frole else None
            if (not frole) or (role.id == getattr(frole, 'id', 0)):
                frole = discord.Object(id=0)

            if (not was_streaming) and is_streaming:
                # member started streaming
                if (frole.id != 0) and (not discord.utils.get(after.roles, id=frole.id)):
                    return  # member doesn't have the filter role

                await after.add_roles(role, reason='Started stream on Twitch')
                self.log.info(
                    'Added role %i to %i in %i',
                    role.id, after.id, after.guild.id)
                await functions.dogstatsd.increment('bot.live_role.role_add_event')

                if liverole.get('notifications') is True:
                    channel = after.guild.get_channel(int(liverole.get('notif_channel', 0)))
                    if channel is None:
                        return

                    game = discord.utils.find(
                        lambda a: a.type == discord.ActivityType.playing and hasattr(a, 'name'),
                        after.activities)
                    if game is not None:
                        gname = game.name.replace('_', '\\_')
                    else:
                        gname = 'nothing'
                    twitch_name = getattr(after_activity, 'twitch_name', 'unknown').replace('_', '\\_')
                    twitch_url = getattr(after_activity, 'url', 'unknown')
                    stream_title = getattr(after_activity, 'details', 'unknown').replace('_', '\\_')

                    fmt_vars = {
                        '{user.name}': after.name.replace('_', '\\_'),
                        '{user.twitch_name}': twitch_name,
                        '{user.twitch_url}': twitch_url,
                        '{user.stream_title}': stream_title,
                        '{user.game}': gname
                    }
                    msg = functions.replace_multiple(liverole['notif_message'], fmt_vars)
                    await channel.send(msg)
                    await functions.dogstatsd.increment('bot.live_role.notification_event')
                    return
            elif was_streaming and (not is_streaming):
                # member is no longer streaming
                if discord.utils.get(after.roles, id=role.id) is None:
                    # member doesn't have the live role, don't try to remove it
                    return
                await after.remove_roles(role, reason='Finished stream on Twitch')
                self.log.info(
                    'Removed role %i from %i in %i',
                    role.id, after.id, after.guild.id)
                await functions.dogstatsd.increment('bot.live_role.role_remove_event')
        except discord.Forbidden as e:
            inf = {
                'text': e.text,
                'status': e.status,
                'code': e.code
            }
            self.log.info('Missing permissions: %i in %i (%s)', after.id, after.guild.id, str(inf))
            await r.table('live_role') \
                .get(str(after.guild.id)) \
                .update({'error': inf}) \
                .run(self.bot.rethink, noreply=True, durability='soft')
        except discord.NotFound as e:
            inf = {
                'text': e.text,
                'status': e.status,
                'code': e.code
            }
            self.log.info('Role not found in %i (%s)', after.guild.id, str(inf))
            await r.table('live_role') \
                .get(str(after.guild.id)) \
                .update({'error': inf}) \
                .run(self.bot.rethink, noreply=True, durability='soft')
        except Exception:
            self.log.exception('Failed to update live role for %i in %i', after.id, after.guild.id)
            await functions.dogstatsd.create_event(
                title="Live role error",
                text=traceback.format_exc(),
                alert_type="error")

    @commands.group(no_pm=True, aliases=['lr', 'lc', 'live_check'])
    async def live_role(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(embed=lang.EmbedBuilder(msgs['live_role']['command_usage']))

    @live_role.command()
    async def set(self, ctx, *, role: typing.Union[discord.Role, str] = None):
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(
                msgs['permissions']['user_need_perm'].format(permission=msgs['permissions']['manage_server']))
        if not ctx.guild.me.permissions_in(ctx.channel).manage_roles:
            return await ctx.send(
                msgs['permissions']['bot_need_perm'].format(permission=msgs['permissions']['manage_roles']))

        if role is None:
            return await ctx.send(msgs['live_role']['no_role_mentioned'])
        if isinstance(role, str):
            role = discord.utils.find(
                lambda m: role.lower() in m.name.lower(),
                ctx.guild.roles
            )
            if role is None:
                return await ctx.send(msgs['live_role']['role_not_found'])

        await r.table('live_role') \
            .insert({
                "id": str(ctx.guild.id),
                "role": str(role.id)
            }, conflict="update") \
            .run(self.bot.rethink, durability="soft", noreply=True)

        await ctx.send(msgs['live_role']['add_success'].format(role=role.name))
        cursor = await r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink)
        if cursor is None:
            # database hasn't updated yet
            return
        g = ctx.guild
        try:
            lc = int(cursor['role'])
            role = discord.utils.find(lambda r: r.id == int(lc), g.roles)
            streamers = list(filter(self.streaming_predicate, g.members))
            msg = await ctx.send(f'{lang.emoji.loading}Adding the live role to {len(streamers)} people... This may take a while.')
            for m in streamers:
                if not m.bot:
                    if 'filter' in cursor.keys():
                        frole = discord.utils.get(g.roles, id=int(cursor['filter']))
                        if frole.id not in map(lambda r: r.id, m.roles):
                            continue
                    await m.add_roles(role, reason="User went live on Twitch")
                    self.log.info('Added live role to %i in %i', m.id, m.guild.id)
            await msg.edit(content=f'{lang.emoji.cmd_success}Finished updating roles')
        except discord.Forbidden:
            await ctx.send(msgs['live_role']['missing_perms_ext'])
        except Exception:
            logging.exception('w')
            raise

    @live_role.command(name="filter", no_pm=True)
    async def _filter(self, ctx, *, role: typing.Union[discord.Role, str] = None):
        """Restricts Live Role to users with a specific role"""
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(
                msgs['permissions']['user_need_perm'].format(permission=msgs['permissions']['manage_server']))
        if not ctx.guild.me.permissions_in(ctx.channel).manage_roles:
            return await ctx.send(
                msgs['permissions']['bot_need_perm'].format(permission=msgs['permissions']['manage_roles']))
        if role is None:
            return await ctx.send(msgs['live_role']['no_role_mentioned'])

        if isinstance(role, str):
            role = discord.utils.find(
                lambda m: role.lower() in m.name.lower(),
                ctx.guild.roles
            )
            if role is None:
                return await ctx.send(msgs['live_role']['role_not_found'])
        cursor = await r.table('live_role') \
            .get(str(ctx.guild.id)) \
            .run(self.bot.rethink)
        cursor = dict(cursor or {})
        if cursor == {}:
            return await ctx.send(msgs['live_role']['not_set_up'])
        if cursor.get('role') == str(role.id):
            return await ctx.send(msgs['live_role']['conflicting_roles'])
        await r.table('live_role') \
            .insert(
                {"id": str(ctx.guild.id), "filter": str(role.id)},
                conflict="update"
            ) \
            .run(self.bot.rethink, durability="soft", noreply=True)
        await ctx.send(msgs['live_role']['filter_success'])
        g = ctx.guild
        lc = int(cursor['role'])
        live_role = discord.utils.find(
            lambda r: str(r.id) == str(lc),
            g.roles
        )
        filtered_members = filter(
            lambda m: role.id in map(lambda r: r.id, m.roles),
            g.members
        )
        for m in filtered_members:
            if role.id is not None and role.id not in map(lambda r: r.id, m.roles):
                await m.remove_roles(live_role, reason="User needs filter role")
                self.log.info('Removed live role from %i in %i due to new filter rule', m.id, m.guild.id)

    @live_role.command(aliases=['del', 'remove'])
    async def delete(self, ctx):
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(
                msgs['permissions']['user_need_perm'].format(permission=msgs['permissions']['manage_server']))
        try:
            await r.table('live_role') \
                .get(str(ctx.guild.id)) \
                .delete() \
                .run(self.bot.rethink, durability="soft", noreply=True)
        except KeyError:
            return await ctx.send(msgs['live_role']['not_set_up'])
        else:
            return await ctx.send(msgs['live_role']['del_success'])

    @live_role.command(aliases=['list'])
    async def view(self, ctx):
        msgs = await lang.get_lang(ctx)
        cursor = await r.table('live_role')\
            .get(str(ctx.guild.id))\
            .run(self.bot.rethink)
        if cursor is None:
            return await ctx.send(msgs['live_role']['not_set_up'])
        role = discord.utils.find(
            lambda n: n.id == int(cursor.get('role', 0)),
            ctx.guild.roles)
        if role is None:
            return await ctx.send(msgs['live_role']['not_set_up'])
        await ctx.send(msgs['live_role']['view_response'].format(role=role.name))

    @live_role.command()
    async def check(self, ctx):
        msgs = await lang.get_lang(ctx)
        cursor = await r.table('live_role')\
            .get(str(ctx.guild.id))\
            .run(self.bot.rethink)
        if cursor is None:
            return await ctx.send(msgs['live_role']['not_set_up'])
        try:
            role = ctx.guild.get_role(int(cursor['role']))
            if cursor.get('filter') is not None:
                frole = ctx.guild.get_role(int(cursor['filter']))
            else:
                frole = None
        except TypeError:
            return await ctx.send(msgs['live_role']['not_set_up'])
        streamers = len(list(filter(self.streaming_predicate, ctx.guild.members)))
        members_with_lr = len([m for m in ctx.guild.members if role in m.roles])
        tracked = discord.utils.find(lambda x: x['id'] == str(ctx.guild.id), self.bot.live_role)
        e = discord.Embed(
            color=0x6441A4,
            title='Live Role Check',
            description=f'Database:\n```json\n{json.dumps(cursor)}\n```\nLocal:\n```json\n{json.dumps(tracked)}\n```\n{repr(role)}\n{repr(frole)}')
        e.set_footer(text=f'{members_with_lr} / {streamers} members with live role')
        await ctx.send(embed=e)


def setup(bot: commands.Bot):
    bot.add_cog(LiveRole(bot))
