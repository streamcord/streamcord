from discord.ext import commands
import discord, asyncio
import urllib.parse
from urllib.parse import urlencode
from random import choice
import logging, traceback
import re
from utils import settings, lang, http
import requests
import secrets

class Users(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile('^\w+$')
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
            e = discord.Embed(color=discord.Color(0x6441A4))
            # get user info
            r = http.TwitchAPIRequest("https://api.twitch.tv/helix/users?login=" + user)
            if r.json().get("data") == [] or r.status_code == 400 or len(r.json()['data']) == 0:
                return await ctx.send(msgs['notifs']['twitch_user_not_found_alt'])
            r.raise_for_status()
            r = r.json()["data"][0]
            # get user streaming status
            s = http.TwitchAPIRequest("https://api.twitch.tv/helix/streams?user_login=" + user)
            s.raise_for_status()
            s = s.json()["data"]
            # get user follows
            ft = http.TwitchAPIRequest("https://api.twitch.tv/helix/users/follows?first=1&to_id=" + r['id'])
            ft.raise_for_status()
            # get user following
            ff = http.TwitchAPIRequest("https://api.twitch.tv/helix/users/follows?first=1&from_id=" + r['id'])
            ff.raise_for_status()
            emote = self.badges.get(r['type'] or r['broadcaster_type'], '')
            e.set_author(icon_url=r["profile_image_url"], name=r["display_name"], url="https://twitch.tv/{}".format(r["login"]))
            e.set_thumbnail(url=r["profile_image_url"])
            e.title = r["login"] + emote
            e.description = r["description"]
            e.add_field(name=msgs['users']['followers'], value="{:,}".format(ft.json()['total']))
            e.add_field(name=msgs['users']['following'], value="{:,}".format(ff.json()['total']))
            e.add_field(name=msgs['users']['views'], value="{:,}".format(r["view_count"]))
            if not s == []:
                s = s[0]
                # get stream tags
                t = http.TwitchAPIRequest(f"https://api.twitch.tv/helix/streams/tags?broadcaster_id={r['id']}")
                t.raise_for_status()
                tag_text = []
                for tag in t.json()['data']:
                    if not tag['is_auto']:
                        tag_text.append(f"[{tag['localization_names']['en-us']}](https://www.twitch.tv/directory/all/tags/{tag['tag_id']})")
                if tag_text == []:
                    tag_text = ["No stream tags"]
                e.add_field(inline=False, name=msgs['users']['tags'], value=", ".join(tag_text))
                # get game info
                g = http.TwitchAPIRequest(f"https://api.twitch.tv/helix/games?id={s['game_id']}")
                g.raise_for_status()
                try:
                    g = g.json()["data"][0]
                except:
                    g = {"name": msgs['users']['unknown']}
                e.add_field(inline=False, name=msgs['users']['live'], value=f"**{s['title']}**\n" + msgs['users']['playing'].format(game=g['name'], view_count=s['viewer_count']) + f"\n\n**[{msgs['users']['watch_on_twitch']}](https://twitch.tv/{user})**")
                e.set_image(url=s['thumbnail_url'].format(width=1920, height=1080) + f"?{secrets.token_urlsafe(5)}")
            else:
                e.add_field(inline=False, name=msgs['users']['not_live'], value=f"[{msgs['users']['view_profile']}](https://twitch.tv/{user})")
                e.set_image(url=r['offline_image_url'])
            e.set_footer(text=f"{msgs['users']['streamer_id']} {r['id']}")
            await ctx.send(embed=e)
        except:
            await ctx.send(traceback.format_exc())

    @commands.command()
    async def connections(self, ctx, *, user: discord.User = None):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        if user is None:
            user = ctx.author
        r = requests.get("http://dash.twitchbot.io/api/connections/{}".format(user.id), headers={"X-Access-Token": settings.DashboardKey})
        if r.status_code == 404:
            return await ctx.send(embed=discord.Embed(description=msgs['users']['no_login_dash'], color=discord.Color.red()))
        r.raise_for_status()
        e = discord.Embed(color=discord.Color(0x6441A4))
        e.set_author(icon_url=user.avatar_url or user.default_avatar_url, name=msgs['users']['connections'].format(user=user))
        r = r.json()
        if r['twitch'] == None or r.get('twitch', {'visibility': 0})['visibility'] == 0:
            e.add_field(name="Twitch", value=msgs['users']['not_connected'], inline=False)
        else:
            e.add_field(name="Twitch", value=msgs['users']['connected'].format(account=r['twitch']['name']), inline=False)
        if r['streamlabs'] == None:
            e.add_field(name="Streamlabs", value=msgs['users']['not_connected'], inline=False)
        else:
            e.add_field(name="Streamlabs", value=msgs['users']['connected'].format(account=r['streamlabs']['streamlabs']['display_name']), inline=False)
        e.set_footer(text="dash.twitchbot.io")
        await ctx.send(embed=e)

class Streams(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group()
    async def stream(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(embed=lang.EmbedBuilder(msgs['streams']['command_usage']))

    @stream.command()
    async def user(self, ctx, *, user):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        user = user.split('/')[-1]
        e = discord.Embed(color=discord.Color(0x6441A4))
        r = http.TwitchAPIRequest("https://api.twitch.tv/helix/streams?user_login=" + user)
        r.raise_for_status()
        if r.json().get("data") in [[], None]:
            await ctx.send(msgs['streams']['stream_not_found'])
        else:
            r = r.json()["data"][0]
            u = http.TwitchAPIRequest("https://api.twitch.tv/helix/users?login=" + user)
            u.raise_for_status()
            u = u.json()["data"][0]
            g = http.TwitchAPIRequest("https://api.twitch.tv/helix/games?id=" + r["game_id"])
            g.raise_for_status()
            try:
                g = g.json()["data"][0]
            except:
                g = {"id": 0, "name": "Unknown"}
            e.set_author(icon_url=u["profile_image_url"], name=u["display_name"], url="https://twitch.tv/{}".format(u["login"]))
            e.title = r["title"]
            e.description = msgs['streams']['stream_desc'].format(game=g['name'], view_count=r['viewer_count'], channel=u['login'])
            e.set_image(url=r["thumbnail_url"].format(width="1920", height="1080") + f"?{secrets.token_urlsafe(5)}")
            await ctx.send(embed=e)

    @stream.command()
    async def watch(self, ctx, *, user):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        user = user.split('/')[-1]
        r = http.TwitchAPIRequest("https://api.twitch.tv/helix/streams?user_login=" + user)
        r.raise_for_status()
        if r.json()["data"] == []:
            await ctx.send(msgs['streams']['stream_not_found'])
        else:
            await ctx.send(f"**<:twitch:404633403603025921> {msgs['streams']['live']}**\nhttps://twitch.tv/{user}")

    @stream.command()
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def game(self, ctx, *, name):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        g = http.TwitchAPIRequest("https://api.twitch.tv/helix/games?" + urllib.parse.urlencode({"name": name}))
        g.raise_for_status()
        try:
            g = g.json()['data'][0]
        except:
            return await ctx.send(msgs['streams']['game_not_found'])
        game = g['name']
        s = http.TwitchAPIRequest("https://api.twitch.tv/helix/streams?game_id=" + g['id'])
        s.raise_for_status()
        if len(s.json()['data']) < 1:
            return await ctx.send(msgs['streams']['game_no_streams'])
        stream = choice(s.json()['data'])
        u = http.TwitchAPIRequest("https://api.twitch.tv/helix/users?id=" + stream['user_id'])
        u.raise_for_status()
        u = u.json()['data'][0]
        await ctx.send(msgs['streams']['game_desc'].format(user=u['display_name'].replace("_", "\\_"), game=game, view_count=stream['viewer_count']))

    @stream.command()
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def top(self, ctx):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        r = http.TwitchAPIRequest("https://api.twitch.tv/helix/streams?first=20")
        r.raise_for_status()
        stream = choice(r.json()['data'])
        u = http.TwitchAPIRequest("https://api.twitch.tv/helix/users?id=" + stream['user_id'])
        u.raise_for_status()
        u = u.json()["data"][0]
        g = http.TwitchAPIRequest("https://api.twitch.tv/helix/games?id=" + stream["game_id"])
        g.raise_for_status()
        g = g.json()["data"][0]
        return await ctx.send(msgs['streams']['game_desc'].format(user=u['login'], game=g['name'], view_count=stream['viewer_count']))

class Clips(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile('^\w+$')

    @commands.group(pass_context=True, aliases=["clip"])
    async def clips(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(embed=lang.EmbedBuilder(msgs['clips']['command_usage']))

    @clips.command(pass_context=True, name="from", aliases=["channel"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def _from(self, ctx, twitch_user: str, *args):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        twitch_user = twitch_user.split('/')[-1]
        if self.regex.match(twitch_user) is None:
            return await ctx.send(msgs['notifs']['malformed_user'])
        trending = ""
        if "--trending" in args:
            trending = "&trending=true"
        r = http.TwitchAPIRequest("https://api.twitch.tv/kraken/clips/top?limit=50&channel=" + twitch_user + trending)
        if r.status_code != 200:
            await ctx.send(f"{msgs['games']['generic_error']} {r.status_code}")
        elif len(r.json()['clips']) < 1:
            await ctx.send(msgs['clips']['no_clips'])
            return
        else:
            clip = choice(r.json()['clips'])
            m = await ctx.send(msgs['clips']['clip_message'].format(user=clip['broadcaster']['display_name'], game=clip['game'], url=clip['url'].split('?')[0]))

    @clips.command(pass_context=True, aliases=["popular", "top"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def trending(self, ctx):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        r = http.TwitchAPIRequest("https://api.twitch.tv/kraken/clips/top?limit=50")
        if r.status_code != 200:
            await ctx.send(f"{msgs['games']['generic_error']} {r.status_code}")
        elif len(r.json()['clips']) < 1:
            await ctx.send(msgs['clips']['no_clips'])
            return
        else:
            clip = choice(r.json()['clips'])
            m = await ctx.send(msgs['clips']['clip_message'].format(user=clip['broadcaster']['display_name'], game=clip['game'], url=clip['url'].split('?')[0]))

    @clips.command(pass_context=True, aliases=["playing"])
    @commands.cooldown(per=3, rate=1, type=commands.BucketType.user)
    async def game(self, ctx, *, game):
        await ctx.trigger_typing()
        msgs = await lang.get_lang(ctx)
        trending = ""
        if game.endswith(" --trending"):
            trending = "&trending=true"
        r = http.TwitchAPIRequest("https://api.twitch.tv/kraken/search/games?" + urlencode({"query": game.strip(' --trending')}))
        if r.status_code != 200:
            await ctx.send(f"{msgs['games']['generic_error']} {r.status_code}-1")
            return
        elif r.json().get('games') == None:
            return await ctx.send(msgs['streams']['game_not_found'])
        elif len(r.json()['games']) < 1:
            await ctx.send(msgs['clips']['no_clips'])
            return
        game = r.json()['games'][0]['name']
        r = http.TwitchAPIRequest("https://api.twitch.tv/kraken/clips/top?limit=50&" + urlencode({"game": game}) + trending)
        if r.status_code != 200:
            await ctx.send(f"{msgs['games']['generic_error']} {r.status_code}-2")
            return
        elif len(r.json()['clips']) < 1:
            await ctx.send(msgs['clips']['no_clips'])
            return
        clip = choice(r.json()['clips'])
        m = await ctx.send(msgs['clips']['clip_message'].format(user=clip['broadcaster']['display_name'], game=clip['game'], url=clip['url'].split('?')[0]))

def setup(bot):
    bot.add_cog(Clips(bot))
    bot.add_cog(Streams(bot))
    bot.add_cog(Users(bot))
