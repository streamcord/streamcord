import re
import secrets
import traceback
from os import getenv
from random import choice

import discord
from discord.ext import commands
import requests
from ..utils import lang


class Users(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile(r'^\w+$')
        self.badges = {
            'staff': ' <:twitch_staff:534168627348504623>',
            'admin': ' <:twitch_admin:534168627541180426>',
            'global_mod': ' <:twitch_global_mod:534168627650232340>',
            'partner': ' <:twitch_verified:409725750116089876>'
        }

    @commands.command(pass_context=True, aliases=["channel"])
    async def user(self, ctx, *, user):
        try:
            await ctx.trigger_typing()
            msgs = await lang.get_lang(ctx)
            user = user.split('/')[-1]
            if self.regex.match(user) is None:
                return await ctx.send(msgs['notifs']['malformed_user'])

            # get user info
            r = await self.bot.chttp_twitch.get('/users', {'login': user})
            rj = (await r.json())
            if not rj.get("data", False) or r.status == 400:
                # twitch user doesn't exist
                return await ctx.send(
                    msgs['notifs']['twitch_user_not_found_alt'])
            r.raise_for_status()
            rj = rj['data'][0]
            # get user streaming status
            s = await self.bot.chttp_twitch.get('/streams', {'user_login': user})
            s.raise_for_status()
            s = (await s.json())["data"]
            # get user follows
            ft = await self.bot.chttp_twitch.get('/users/follows', {'first': 1, 'to_id': rj['id']})
            ft.raise_for_status()
            # get user following
            ff = await self.bot.chttp_twitch.get('/users/follows', {'first': 1, 'from_id': rj['id']})
            ff.raise_for_status()

            emote = self.badges.get(rj['type'] or rj['broadcaster_type'], '')
            e = discord.Embed(
                color=discord.Color(0x6441A4),
                title=rj['login'] + emote,
                description=rj['description'])
            e.set_author(
                icon_url=rj["profile_image_url"],
                name=rj["display_name"],
                url=f"https://twitch.tv/{rj['login']}")
            e.set_thumbnail(url=rj["profile_image_url"])
            e.add_field(
                name=msgs['users']['followers'],
                value="{:,}".format((await ft.json())['total']))
            e.add_field(
                name=msgs['users']['following'],
                value="{:,}".format((await ff.json())['total']))
            e.add_field(
                name=msgs['users']['views'],
                value="{:,}".format(rj["view_count"]))

            if s:
                # add stream tags; user is streaming
                s = s[0]
                t = await self.bot.chttp_twitch.get('/streams/tags', {'broadcaster_id': rj['id']})
                t.raise_for_status()
                tag_text = []
                for tag in (await t.json())['data']:
                    if not tag['is_auto']:
                        tag_text.append(f"[{tag['localization_names']['en-us']}](https://www.twitch.tv/directory/all/tags/{tag['tag_id']})")
                if tag_text == []:
                    tag_text = ["No stream tags"]
                e.add_field(
                    inline=False,
                    name=msgs['users']['tags'],
                    value=", ".join(tag_text))
                # get game info
                g = await self.bot.chttp_twitch.get('/games', {'id': s['game_id']})
                g.raise_for_status()
                try:
                    g = (await g.json())["data"][0]
                except Exception:
                    g = {"name": msgs['users']['unknown']}
                e.add_field(
                    inline=False,
                    name=msgs['users']['live'],
                    value=f"**{s['title']}**\n"
                    + msgs['users']['playing'].format(game=g['name'], view_count=s['viewer_count'])
                    + f"\n\n**[{msgs['users']['watch_on_twitch']}](https://twitch.tv/{user})**")
                e.set_image(
                    url=s['thumbnail_url'].format(width=1920, height=1080) + f"?{secrets.token_urlsafe(5)}")
            else:
                e.add_field(
                    inline=False,
                    name=msgs['users']['not_live'],
                    value=f"[{msgs['users']['view_profile']}](https://twitch.tv/{user})")
                e.set_image(url=rj['offline_image_url'])
            e.set_footer(text=f"{msgs['users']['streamer_id']} {rj['id']}")
            await ctx.send(embed=e)
        except Exception:
            await ctx.send(traceback.format_exc())

    @commands.command()
    async def connections(self, ctx, *, user: discord.User = None):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        if user is None:
            user = ctx.author
        r = requests.get(
            f"http://dash.streamcord.io/api/connections/{user.id}",
            headers={"X-Access-Token": getenv('DASHBOARD_KEY')})
        if r.status_code == 404:
            return await ctx.send(
                embed=discord.Embed(
                    description=msgs['users']['no_login_dash'],
                    color=discord.Color.red()))
        r.raise_for_status()
        e = discord.Embed(color=discord.Color(0x6441A4))
        e.set_author(
            icon_url=user.avatar_url or user.default_avatar_url,
            name=msgs['users']['connections'].format(user=user))
        r = r.json()
        if r['twitch'] is None or r.get('twitch', {'visibility': 0})['visibility'] == 0:
            e.add_field(
                name="Twitch",
                value=msgs['users']['not_connected'],
                inline=False)
        else:
            e.add_field(
                name="Twitch",
                value=msgs['users']['connected'].format(
                    account=r['twitch']['name']),
                inline=False)
        if r['streamlabs'] is None:
            e.add_field(
                name="Streamlabs",
                value=msgs['users']['not_connected'],
                inline=False)
        else:
            e.add_field(
                name="Streamlabs",
                value=msgs['users']['connected'].format(
                    account=r['streamlabs']['streamlabs']['display_name']),
                inline=False)
        e.set_footer(text="dash.streamcord.io")
        await ctx.send(embed=e)


class Streams(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def stream(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(
                embed=lang.EmbedBuilder(msgs['streams']['command_usage']))

    @stream.command()
    async def user(self, ctx, *, user):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        user = user.split('/')[-1]
        r = await self.bot.chttp_twitch.get('/streams', {'user_login': user})
        r.raise_for_status()
        r = await r.json()
        if not r.get("data"):
            await ctx.send(msgs['streams']['stream_not_found'])
        else:
            r = r["data"][0]
            u = await self.bot.chttp_twitch.get('/users', {'login': user})
            u.raise_for_status()
            u = (await u.json())["data"][0]
            g = await self.bot.chttp_twitch.get('/games', {'id': r['game_id']})
            g.raise_for_status()
            try:
                g = (await g.json())["data"][0]
            except Exception:
                g = {"id": 0, "name": "Unknown"}

            e = discord.Embed(
                color=discord.Color(0x6441A4),
                title=r['title'],
                description=msgs['streams']['stream_desc'].format(
                    game=g['name'],
                    view_count=r['viewer_count'],
                    channel=u['login']))
            e.set_author(
                icon_url=u["profile_image_url"],
                name=u["display_name"],
                url=f"https://twitch.tv/{u['login']}")
            e.set_image(
                url=r["thumbnail_url"].format(width="1920", height="1080")
                + f"?{secrets.token_urlsafe(5)}")
            await ctx.send(embed=e)

    @stream.command()
    async def watch(self, ctx, *, user):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        user = user.split('/')[-1]
        r = await self.bot.chttp_twitch.get('/streams', {'user_login': user})
        r.raise_for_status()
        r = await r.json()
        if not r.get('data'):
            await ctx.send(msgs['streams']['stream_not_found'])
        else:
            await ctx.send(f"{lang.emoji.twitch_icon} **{msgs['streams']['live']}**\nhttps://twitch.tv/{user}")

    @stream.command()
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def game(self, ctx, *, name):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        g = await self.bot.chttp_twitch.get('/games', {'name': name})
        g.raise_for_status()
        try:
            g = (await g.json())['data'][0]
        except Exception:
            return await ctx.send(msgs['streams']['game_not_found'])
        game = g['name']
        s = await self.bot.chttp_twitch.get('/streams', {'game_id': g['id']})
        s.raise_for_status()
        s = await s.json()
        if not s.get('data'):
            return await ctx.send(msgs['streams']['game_no_streams'])
        stream = choice(s['data'])
        u = await self.bot.chttp_twitch.get('/users', {'id': stream['user_id']})
        u.raise_for_status()
        u = (await u.json())['data'][0]
        await ctx.send(
            msgs['streams']['game_desc'].format(
                user=u['display_name'].replace("_", "\\_"),
                game=game,
                view_count=stream['viewer_count']))

    @stream.command()
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def top(self, ctx):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        r = await self.bot.chttp_twitch.get('/streams', {'first': 20})
        r.raise_for_status()
        stream = choice((await r.json())['data'])
        u = await self.bot.chttp_twitch.get('/users', {'id': stream['user_id']})
        u.raise_for_status()
        u = (await u.json())["data"][0]
        g = await self.bot.chttp_twitch.get('/games', {'id': stream['game_id']})
        g.raise_for_status()
        g = (await g.json())["data"][0]
        return await ctx.send(
            msgs['streams']['game_desc'].format(
                user=u['login'],
                game=g['name'],
                view_count=stream['viewer_count']))


class Clips(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile(r'^\w+$')

    @commands.group(pass_context=True, aliases=["clip"])
    async def clips(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(
                embed=lang.EmbedBuilder(msgs['clips']['command_usage']))

    @clips.command(pass_context=True, name="from", aliases=["channel"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def _from(self, ctx, twitch_user: str):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        twitch_user = twitch_user.split('/')[-1]
        if self.regex.match(twitch_user) is None:
            return await ctx.send(msgs['notifs']['malformed_user'])
        r = await self.bot.chttp_twitch.get('/clips/top', {'limit': 50, 'channel': twitch_user}, is_v5=True)
        if r.status > 399:
            return await ctx.send(f"{msgs['games']['generic_error']} {r.status}")
        r = await r.json()
        if not r.get('clips', False):
            return await ctx.send(msgs['clips']['no_clips'])
        clip = choice(r['clips'])
        await ctx.send(
            msgs['clips']['clip_message'].format(
                user=clip['broadcaster']['display_name'],
                game=clip['game'],
                url=clip['url'].split('?')[0]))

    @clips.command(pass_context=True, aliases=["popular", "top"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def trending(self, ctx):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        r = await self.bot.chttp_twitch.get('/clips/top', {'limit': 50}, is_v5=True)
        if r.status > 399:
            await ctx.send(f"{msgs['games']['generic_error']} {r.status}")
        r = await r.json()
        if not r.get('clips', False):
            return await ctx.send(msgs['clips']['no_clips'])
        clip = choice(r['clips'])
        await ctx.send(
            msgs['clips']['clip_message'].format(
                user=clip['broadcaster']['display_name'],
                game=clip['game'],
                url=clip['url'].split('?')[0]))

    @clips.command(pass_context=True, aliases=["playing"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def game(self, ctx, *, game):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        r = await self.bot.chttp_twitch.get('/search/games', {'query': game}, is_v5=True)
        if r.status > 399:
            return await ctx.send(f"{msgs['games']['generic_error']} {r.status}-1")
        r = await r.json()
        if not r.get('games', False):
            return await ctx.send(msgs['clips']['no_clips'])
        game = r['games'][0]['name']
        r = await self.bot.chttp_twitch.get('/clips/top', {'limit': 50, 'game': game}, is_v5=True)
        if r.status > 399:
            return await ctx.send(f"{msgs['games']['generic_error']} {r.status}-2")
        r = await r.json()
        if not r.get('clips', False):
            await ctx.send(msgs['clips']['no_clips'])
            return
        clip = choice(r['clips'])
        await ctx.send(
            msgs['clips']['clip_message'].format(
                user=clip['broadcaster']['display_name'],
                game=clip['game'],
                url=clip['url'].split('?')[0]))


def setup(bot):
    bot.add_cog(Clips(bot))
    bot.add_cog(Streams(bot))
    bot.add_cog(Users(bot))
