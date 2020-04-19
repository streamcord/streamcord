import asyncio
import datetime
import discord
import logging
import time

from discord.ext import commands
from secrets import token_hex
from typing import Optional
from ..utils import functions
from .. import TwitchBot


class LiveRole(commands.Cog):
    def __init__(self, bot):
        self.bot: TwitchBot = bot
        self.live_role = {}
        self.bot._live_role_nonce = None
        self._last_fetch = None

        self.log = logging.getLogger('bot.live_role')
        self.bot.loop.create_task(self._pull_cache_loop())

    @staticmethod
    def _activity_base(activity: discord.Activity) -> bool:
        return isinstance(activity, discord.Streaming)

    @staticmethod
    def _streaming_base(member: discord.Member) -> bool:
        """
        Returns True if the member is eligible to receive the live role
        """
        if member.bot:
            return False
        return any([isinstance(a, discord.Streaming) for a in member.activities])

    async def _pull_cache(self):
        c_time = time.time()
        self.live_role = {guild.pop('_id'): guild async for guild in self.bot.db.liveRole.find({})}
        self.log.info('Updated live role cache in %sms (%s guilds)',
                      round((time.time() - c_time) * 1000), len(self.live_role))
        self._last_fetch = datetime.datetime.utcnow()

    async def _pull_cache_loop(self):
        # when reloading a cog, old tasks are never cleaned up. so, we need to make sure that only the most recent
        # cache update loop is running
        _nonce = token_hex(6)
        self.bot._live_role_nonce = _nonce
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            if self.bot._live_role_nonce != _nonce:
                self.log.info('Replacing live role update task %s with %s', _nonce, self.bot._live_role_nonce)
                break
            try:
                await self._pull_cache()
            except Exception:
                self.log.exception('Failed to retrieve live role!! Retrying in 120s')
            await asyncio.sleep(60)
        self.log.info('Cleaned up live role task %s', _nonce)

    async def _handle_stream_end(self, member: discord.Member, live_role: discord.Role):
        if not discord.utils.get(member.roles, id=live_role.id):
            # user doesn't have the live role, so don't try to remove it
            return

        try:
            await member.remove_roles(live_role, reason='[Live role] Stream ended on Twitch')
        except discord.Forbidden as ex:
            # TODO: Error logging
            pass
        except discord.NotFound:
            pass
        except Exception:
            self.log.exception('Failed to remove live role from %s in %s', member.id, member.guild.id)
            return
        finally:
            self.log.info('Removed role %s from %s in %s', live_role.id, member.id, member.guild.id)
            await functions.dogstatsd.increment('bot.live_role.role_remove_event')

    async def _handle_stream_start(self, member: discord.Member, activity: discord.Streaming, live_role: discord.Role,
                                   filter_role: Optional[discord.Role], config: dict):
        if filter_role:
            has_filter = discord.utils.get(member.roles, id=filter_role.id) is not None
            if not has_filter:
                return

        try:
            await member.add_roles(live_role, reason='[Live role] Started stream on Twitch')
        except discord.Forbidden as ex:
            # TODO: Error logging
            pass
        except discord.NotFound:
            pass
        except Exception:
            self.log.exception('Failed to add live role to %s in %s', member.id, member.guild.id)
            return
        finally:
            self.log.info('Added role %s to %s in %s', live_role.id, member.id, member.guild.id)
            await functions.dogstatsd.increment('bot.live_role.role_add_event')

        if config.get('notifs'):
            await self._make_notification(member, activity, config)

    async def _make_notification(self, member: discord.Member, activity: discord.Streaming, config: dict):
        if not config.get('notifs'):
            return
        notifs: dict = config['notifs']
        if not notifs.get('enabled'):
            return
        if not notifs.get('channel'):
            return
        if not notifs.get('message'):
            notifs['message'] = '{user.name} is now live on Twitch! Watch them at {user.twitch_url}'
        channel: discord.TextChannel = member.guild.get_channel(int(notifs['channel']))
        if channel is None:
            return

        fmt_vars = {
            '{user.name}': member.name.replace('_', '\\_'),
            '{user.twitch_name}': (getattr(activity, 'twitch_name') or 'unknown').replace('_', '\\_'),
            '{user.twitch_url}': (getattr(activity, 'url') or 'unknown'),
            '{user.stream_title}': (getattr(activity, 'details') or 'unknown').replace('_', '\\_')
        }
        msg_content = functions.replace_multiple(notifs['message'], fmt_vars)

        try:
            await channel.send(msg_content)
        except discord.Forbidden as ex:
            # TODO: Error logging
            self.log.info('Forbidden')
            pass
        except Exception:
            self.log.exception('Failed to add live role to %s in %s', member.id, member.guild.id)
            return
        finally:
            await functions.dogstatsd.increment('bot.live_role.notification_event')

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild is None or before.bot:
            return
        curr_activity: Optional[discord.Streaming] = discord.utils.find(LiveRole._activity_base, after.activities)
        was_streaming = any([isinstance(a, discord.Streaming) for a in before.activities])
        is_streaming = any([isinstance(a, discord.Streaming) for a in after.activities])

        if was_streaming == is_streaming:
            return
        elif 'twitch' not in str(getattr(curr_activity, 'url', '')):
            # known issue 17:
            # prevent Streamcord from notifying about non-Twitch streamers
            return

        self.log.debug('%s\'s stream state in %s changed from %s to %s',
                       after.id, after.guild.id, was_streaming, is_streaming)

        if not self.live_role:
            self.log.debug('Dropping stream state change event for %s', after.id)
            return

        lr_config = self.live_role.get(str(after.guild.id))
        if lr_config is None or not lr_config.get('role'):
            return

        live_role: discord.Role = after.guild.get_role(int(lr_config['role']))
        if not live_role:
            return
        filter_role: Optional[discord.Role] = None
        if filter_id := lr_config.get('filter'):
            if filter_id != lr_config['role']:
                filter_role = after.guild.get_role(int(filter_id))

        try:
            if is_streaming:
                await self._handle_stream_start(after, curr_activity, live_role, filter_role, lr_config)
            elif was_streaming:
                await self._handle_stream_end(after, live_role)
        except Exception:
            self.log.exception('Live role event error')

    # ----------------- #
    # Commands
    # ----------------- #

    @commands.group(aliases=['lr'])
    @commands.has_permissions(manage_guild=True)
    async def live_role(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.bot.get_command('live_role view'))

    @live_role.command()
    async def view(self, ctx: commands.Context):
        config = await self.bot.db.liveRole.find_one({'_id': str(ctx.guild.id)}) or {}

        live_role: discord.Role = ctx.guild.get_role(int(config.get('role') or 0))
        if live_role is None:
            return await ctx.send('No live role is set up for this server.')
        filter_role: discord.Role = ctx.guild.get_role(int(config.get('filter') or 0))
        lr_notifications = config.get('notifs', {'enabled': False})

        e = discord.Embed(
            color=0x9146ff,
            title='Live role configuration',
            description='You can also manage live role from the '
                        f'[Streamcord Dashboard](https://dash.streamcord.io/servers/{ctx.guild.id})')
        if live_role:
            e.add_field(name='Live role', value=live_role.mention)
        else:
            e.add_field(name='Live role', value='No role')
        if filter_role:
            e.add_field(name='Filter role', value=filter_role.mention)
        else:
            e.add_field(name='Filter role', value='No role')
        if lr_notifications['enabled']:
            notif_channel: discord.TextChannel = ctx.guild.get_channel(int(lr_notifications.get('channel', 0)))
            if notif_channel:
                e.add_field(
                    name='Live role notifications',
                    value=f'**Enabled**\nChannel: {notif_channel.mention}',
                    inline=False)
            else:
                e.add_field(name='Live role notifications', value='**Enabled**\nNo channel configured.', inline=False)
        else:
            e.add_field(
                name='Live role notifications',
                value=f'Disabled',
                inline=False)
        e.set_footer(text='You can set a live role using `!twitch lr set role`')
        await ctx.send(embed=e)

    @live_role.command()
    async def check(self, ctx: commands.Context):
        config = await self.bot.db.liveRole.find_one({'_id': str(ctx.guild.id)}) or {}
        if not config.get('role'):
            return await ctx.send('No live role is set up for this server.')
        try:
            del config['_id']
        except KeyError:
            pass

        live_role: discord.Role = ctx.guild.get_role(int(config.get('role') or 0))
        if not live_role:
            return await ctx.send('No live role is set up for this server.')
        filter_role: Optional[discord.Role] = ctx.guild.get_role(int(config.get('filter') or 0))
        bot_role: discord.Role = discord.utils.get(ctx.guild.me.roles, managed=True)
        perms: discord.Permissions = ctx.guild.me.permissions_in(ctx.channel)

        lr_count = [m for m in ctx.guild.members if any([live_role == r for r in m.roles])]
        streaming_count = [m for m in ctx.guild.members if LiveRole._streaming_base(m)]
        streaming_w_lr_count = [m for m in streaming_count if m in lr_count]
        streaming_wo_lr_count = [m for m in streaming_count if m not in lr_count]
        not_streaming_w_lr_count = [m for m in lr_count if m not in streaming_count]

        e = discord.Embed(
            color=0x9146ff,
            timestamp=self._last_fetch,
            title='Live role check')
        e.add_field(
            name='Database',
            value='```python\n'
                  f'{config}\n'
                  '```',
            inline=False)
        e.add_field(
            name='Local',
            value='```python\n'
                  f'{self.live_role.get(str(ctx.guild.id))}\n'
                  '```',
            inline=False)
        e.add_field(
            name='Roles',
            value=f'Live role: {repr(live_role)}\n'
                  f'Filter role: {repr(filter_role)}\n'
                  f'Streamcord role: {repr(bot_role)}',
            inline=False)
        e.add_field(
            name='Checks',
            value=f'Members with live role: {len(lr_count)}\n'
                  f'Members streaming: {len(streaming_count)}\n'
                  f'Members streaming w/ live role: {len(streaming_w_lr_count)}\n'
                  f'Members streaming w/o live role: {len(streaming_wo_lr_count)}\n'
                  f'Members not streaming w/ live role: {len(not_streaming_w_lr_count)}',
            inline=False)
        e.add_field(
            name='Permissions',
            value=f'Binary value: {perms.value}\n'
                  f' - Administrator: {perms.administrator}\n'
                  f' - Manage roles: {perms.manage_roles}',
            inline=False)
        e.set_footer(text='Last pull: ')
        await ctx.send(embed=e)

    @live_role.command(name='filter')
    async def _filter(self, ctx: commands.Context):
        await ctx.send('This command has been moved, please use the `lr set filter` command instead!')

    @live_role.group(name='set')
    @commands.bot_has_permissions(manage_roles=True)
    async def _set(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send('This command has been moved, please use the `lr set role` command instead!')

    @_set.command()
    async def role(self, ctx: commands.Context, *, role: discord.Role):
        bot_role: discord.Role = discord.utils.get(ctx.guild.me.roles, managed=True)
        if role >= bot_role:
            return await ctx.send('The Streamcord role must be higher than the live role.')
        elif role.managed:
            return await ctx.send('The live role can\'t be managed by an integration.')
        elif role.is_default():
            return await ctx.send('The live role can\'t be the server\'s default role. Use `!twitch lr del` to clear '
                                  'the configuration.')
        async with ctx.typing():
            await self.bot.db.liveRole.update_one(
                {'_id': str(ctx.guild.id)},
                {'$set': {'role': str(role.id)}},
                upsert=True)
        await ctx.send('Server members who stream on Twitch will receive the **{role}** role.'.format(role=role.name))

        # fill roles for members that are already live
        config = await self.bot.db.liveRole.find_one({'_id': str(ctx.guild.id)}) or {}

        role_members = [m for m in ctx.guild.members if config['role'] in [str(r.id) for r in m.roles]]
        member: discord.Member
        for member in role_members:
            if not LiveRole._streaming_base(member):
                # user isn't streaming, so they shouldn't have the live role
                await member.remove_roles(role, reason='[Live role] User is not streaming')
                self.log.info('Removed role from %s: not streaming', member.id)
            elif filter_role := config.get('filter'):
                if filter_role not in [str(r.id) for r in member.roles]:
                    # user doesn't have the filter role
                    await member.remove_roles(role, reason='[Live role] User does not have filter role')
                    self.log.info('Removed role from %s: no filter role', member.id)

        live_members = [m for m in ctx.guild.members if LiveRole._streaming_base(m)]
        if filter_role := config.get('filter'):
            live_members = [m for m in live_members if filter_role in [str(r.id) for r in m.roles]]
        self.log.info('Found %s live members', len(live_members))

        member: discord.Member
        for member in live_members:
            await member.add_roles(role, reason='[Live role] Started stream on Twitch')
            self.log.info('Added live role to %s', member.id)
        await ctx.send('Finished updating member roles.')

    @_set.command(name='filter')
    async def _filter(self, ctx: commands.Context, *, role: discord.Role):
        config = await self.bot.db.liveRole.find_one({'_id': str(ctx.guild.id)}) or {}
        if not config.get('role'):
            return await ctx.send('You must first set a live role using `!twitch lr set role @role-name`')
        elif role.is_default():
            return await ctx.send('The live role can\'t be the server\'s default role. Use `!twitch lr del filter` to '
                                  'clear the filter role.')

        async with ctx.typing():
            await self.bot.db.liveRole.update_one(
                {'_id': str(ctx.guild.id)},
                {'$set': {'filter': str(role.id)}})

        live_role = ctx.guild.get_role(int(config['role']))
        await ctx.send('Server members who stream on Twitch and have the **{filter}** role will receive the'
                       ' **{role}** role.'.format(filter=role.name, role=live_role.name))

    @live_role.group(aliases=['del'])
    async def delete(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            async with ctx.typing():
                await self.bot.db.liveRole.find_one_and_delete({'_id': str(ctx.guild.id)})
            await ctx.send('Removed this server\'s live role configuration.')

    @delete.command(name='filter')
    async def delete_filter(self, ctx: commands.Context):
        async with ctx.typing():
            await self.bot.db.liveRole.update_one(
                {'_id': str(ctx.guild.id)},
                {'$unset': {'filter': ''}})
        await ctx.send('Removed this server\'s filter role configuration.')


def setup(bot: TwitchBot):
    bot.add_cog(LiveRole(bot))
