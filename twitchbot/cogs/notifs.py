import asyncio
import datetime
import discord
import re
import requests
import traceback

from discord.ext import commands
from os import getenv
from rethinkdb import RethinkDB
from ..utils import lang, functions, paginator

r = RethinkDB()
r.set_loop_type('asyncio')


class Notifs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile(r'^\w+$')

    @commands.group(no_pm=True)
    async def notif(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(embed=lang.build_embed(msgs['notifs']['command_usage']))

    @notif.command(no_pm=True)
    async def add(
            self,
            ctx,
            discord_channel: discord.TextChannel = None,
            twitch_user: str = None,
            *,
            msg: str = None
    ):
        msgs = await lang.get_lang(ctx)

        if not ctx.guild:
            return await ctx.send(msgs['permissions']['no_pm'])
        if not ctx.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send(
                msgs['permissions']['user_need_perm'].format(permission=msgs['permissions']['manage_server']))

        if getenv('ENABLE_PRO_FEATURES') == '0':
            # FIXME: Use aiohttp
            prem_check = requests.get(
                f"https://api.streamcord.io/premium/{ctx.author.id}",
                headers={"X-Auth-Key": getenv('DASHBOARD_KEY')})
            is_client_err = 499 >= prem_check.status_code > 299
            if prem_check.json().get('premium') is not True or is_client_err:
                channels = list(map(lambda c: str(c.id), ctx.guild.channels))
                serv_notifs = await r.table('notifications') \
                    .filter(lambda obj: r.expr(channels).contains(obj['channel'])) \
                    .count() \
                    .run(self.bot.rethink)
                if serv_notifs > 25:
                    return await ctx.send(msgs['notifs']['limit_reached'])

        s = None
        username = None
        await ctx.send(msgs['notifs']['dashboard_notice'])
        if discord_channel is None:
            await ctx.send(msgs['notifs']['prompt1'])
            try:
                m = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id,
                    timeout=60)
                discord_channel = discord.utils.find(
                    lambda c: c.name.lower().startswith(m.clean_content.strip("#").lower()),
                    ctx.guild.text_channels)
                if discord_channel is None:
                    return await ctx.send(msgs['notifs']['text_channel_not_found'])
            except asyncio.TimeoutError:
                return await ctx.send(msgs['notifs']['response_timeout'])

        perms = discord_channel.permissions_for(ctx.guild.me)
        check_val = functions.check_permission_set(
            perms,
            "read_messages",
            "send_messages",
            "embed_links",
            "external_emojis"
        )
        if check_val is not True:
            return await ctx.send(
                msgs['permissions']['bot_need_perm'].format(permission=check_val))

        if twitch_user is None:
            await ctx.send(msgs['notifs']['prompt2'])
            try:
                m = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id,
                    timeout=60)
                username = m.content.split('/')[-1]
                s = await self.bot.chttp_twitch.get('/users', {'login': username})
                sjson = await s.json()
                if s.status == 404:
                    return await ctx.send(msgs['notifs']['twitch_user_not_found'])
                if "data" not in sjson.keys():
                    return await ctx.send(f"{msgs['games']['generic_error']} {s.status_code}")
                if not sjson.get('data', False):
                    return await ctx.send(msgs['notifs']['twitch_user_not_found'])
                if s.status > 399:
                    return await ctx.send(f"{msgs['games']['generic_error']} {s.status_code}")
            except asyncio.TimeoutError:
                return await ctx.send(msgs['notifs']['response_timeout'])
        else:
            username = twitch_user.split('/')[-1]
            s = await self.bot.chttp_twitch.get('/users', {'login': username})
            sjson = await s.json()
            if s.status == 404 or not sjson.get('data', False):
                return await ctx.send(msgs['notifs']['twitch_user_not_found'])
        try:
            s = sjson['data'][0]
        except KeyError as e:
            return await ctx.send(
                f"{msgs['notifs']['invalid_data']} noindex-f{str(e)}"
            )
        except IndexError as e:
            return await ctx.send(
                f"{msgs['notifs']['invalid_data']} noindex-f{str(e)}"
            )
        if self.regex.match(username) is None:
            return await ctx.send(msgs['notifs']['malformed_user'])
        if msg is None:
            await ctx.send(msgs['notifs']['prompt3'])
            try:
                m = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.channel == ctx.channel and m.author.id == ctx.author.id,
                    timeout=180)
                if m.content.lower() in ['default', '`default`']:
                    msg = msgs['notifs']['default_msg'].format(channel=username)
                else:
                    msg = m.content
            except asyncio.TimeoutError:
                return await ctx.send(msgs['notifs']['response_timeout'])
        try:
            info = {
                "channel": str(discord_channel.id),
                "streamer": s['id'],
                "name": username,
                "last_stream_id": None,
                "message": msg,
                "guild": str(discord_channel.guild.id)
            }
            existing_notif = r.table('notifications')\
                .filter(
                    (r.row['streamer'] == s['id'])
                    & (r.row['channel'] == str(discord_channel.id))
                )
            if (await existing_notif.count().run(self.bot.rethink)) == 0:
                await r.table('notifications') \
                    .insert(info) \
                    .run(self.bot.rethink, durability="soft", noreply=True)
            else:
                await existing_notif \
                    .update(info) \
                    .run(self.bot.rethink, durability="soft", noreply=True)
            return await ctx.send(
                msgs['notifs']['add_success'].format(
                    user=username,
                    channel=discord_channel.mention))
        except KeyError:
            return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])
        except IndexError:
            return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])

    @notif.command(no_pm=True)
    async def list(self, ctx, channel: discord.TextChannel = None):
        """Lists notifications in the current channel."""

        msgs = await lang.get_lang(ctx)

        if not ctx.guild:
            return await ctx.send(msgs['permissions']['no_pm'])
        channel = channel or ctx.channel

        notifs = await r.table('notifications') \
            .filter(r.row['channel'].eq(str(channel.id))) \
            .run(self.bot.rethink)
        notifs = [x async for x in notifs]
        if not notifs:
            return await ctx.send(msgs['notifs']['no_notifs'])

        e = discord.Embed(
            color=0x9146ff,
            title=msgs['notifs']['list_title'].format(channel=channel.name),
            description=msgs['notifs']['count'].format(num=len(notifs)) + f'\n[{msgs["notifs"]["view_on_dashboard"]}](https://dash.streamcord.io/servers/{ctx.guild.id})'
        )

        for notif in notifs:
            name = notif.get('name', notif['streamer'])
            e.add_field(
                name=f"{name}{' [Beta notification]' if notif.get('is_webhook') else ''}",
                value=notif['message'],
                inline=False)
        pager = paginator.EmbedPaginator(e)
        await pager.page(ctx)

    @notif.command(aliases=["del", "delete"], no_pm=True)
    async def remove(
            self,
            ctx,
            discord_channel: discord.TextChannel,
            twitch_user: str = None,
            *,
            flags=""
    ):
        """Deletes notifications for a Twitch user in the specified channel."""
        msgs = await lang.get_lang(ctx)
        flags = flags.split(" ")
        if not ctx.guild:
            return await ctx.send(msgs['permissions']['no_pm'])
        if not ctx.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send(
                msgs['permissions']['user_need_perm'].format(permission=msgs['permissions']['manage_server']))

        if twitch_user is None:
            notifs = r.table('notifications') \
                .filter(r.row['channel'].eq(str(discord_channel.id)))
            cnt = await notifs \
                .count() \
                .run(self.bot.rethink)
            await ctx.send(
                "⚠️ " + msgs['notifs']['bulk_delete_confirm'].format(
                    count=cnt,
                    channel=discord_channel.mention))
            try:
                m = await self.bot.wait_for(
                    'message',
                    check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id,
                    timeout=60)
                if "yes" not in m.clean_content.lower():
                    return await ctx.send(msgs['notifs']['command_cancelled'])

                await notifs \
                    .delete() \
                    .run(self.bot.rethink, durability="soft", noreply=True)
                return await ctx.send(
                    msgs['notifs']['bulk_delete_success'].format(
                        count=cnt,
                        channel=discord_channel.mention))
            except asyncio.TimeoutError:
                return await ctx.send(msgs['notifs']['response_timeout'])
        else:
            username = twitch_user.split('/')[-1]
            if self.regex.match(username) is None:
                return await ctx.send(msgs['notifs']['malformed_user'])

            try:
                if "--force-user-id" not in flags:
                    s = await self.bot.chttp_twitch.get('/users', {'login': username})
                    if s.status == 404:
                        return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])
                    s = await s.json()
                else:
                    s = {"data": [{"id": twitch_user}]}
                await r.table('notifications') \
                    .filter(
                        (r.row['streamer'] == s['data'][0]['id']) &
                        (r.row['channel'] == str(discord_channel.id))
                    ) \
                    .delete() \
                    .run(self.bot.rethink, durability="soft", noreply=True)
            except KeyError:
                await ctx.send(msgs['notifs']['del_fail'])
            except IndexError:
                await ctx.send(msgs['notifs']['del_fail'])
            except Exception:
                await ctx.send(traceback.format_exc())
            else:
                await ctx.send(msgs['notifs']['del_success'].format(
                    channel=discord_channel.mention,
                    user=username))

    @notif.command()
    async def preview(self, ctx, discord_channel: discord.TextChannel, twitch_user: str):
        """Sends a preview for a notification."""
        msgs = await lang.get_lang(ctx)
        username = twitch_user.split('/')[-1]
        if self.regex.match(username) is None:
            return await ctx.send(msgs['notifs']['malformed_user'])
        await ctx.trigger_typing()

        req = await self.bot.chttp_twitch.get('/users', {'login': username})
        rjson = (await req.json()).get('data', [None])[0]
        if req.status == 404 or not rjson:
            return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])
        if req.status != 200:
            return await ctx.send(f"{msgs['notifs']['invalid_data']} {req.status}")

        notif = r.table('notifications') \
            .filter(
                (r.row['streamer'] == rjson['id']) &
                (r.row['channel'] == str(discord_channel.id))
            )
        if (await notif.count().run(self.bot.rethink)) == 0:
            return await ctx.send(msgs['notifs']['del_fail'])
        notif = [x async for x in await notif.run(self.bot.rethink)][0]

        link = f"https://twitch.tv/{rjson['login']}"
        e = discord.Embed(
            color=discord.Color(0x9146ff),
            title="**Example stream title**",
            description=f"Playing (game) for (viewers) viewers\n[Watch Stream]({link})",
            timestamp=datetime.datetime.utcnow())
        e.set_footer(text="Notification preview")
        e.set_author(
            name=f"{rjson['display_name']} is now live on Twitch!",
            url=link,
            icon_url=rjson['profile_image_url'])
        e.set_image(url="https://images-ext-1.discordapp.net/external/FueXlfSkrjOeYMx92Qe3Y2AaV4G5dk9ijVlNGpF-AgU/https/static-cdn.jtvnw.net/previews-ttv/live_user_overwatchcontenders-1920x1080.jpg")
        fmt_vars = {
            "$title$": "Example stream title",
            "$viewers$": "(viewers)",
            "$game$": "(game)",
            "$url$": link,
            "$name$": rjson['display_name'],
            "$everyone$": "[at]everyone",
            "$here$": "[at]here"
        }
        msg = functions.replace_multiple(notif['message'], fmt_vars)
        msg = functions.replace_multiple(msg, {
            "@everyone": "[at]everyone",
            "@here": "[at]here"
        })
        return await ctx.send(msg, embed=e)

    @notif.command()
    async def formatting(self, ctx):
        msgs = await lang.get_lang(ctx)
        e = lang.build_embed(msgs['notifs']['notif_variables'])
        e.set_footer(
            icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url,
            text=str(ctx.author))
        await ctx.send(embed=e)


def setup(bot: commands.Bot):
    bot.add_cog(Notifs(bot))
