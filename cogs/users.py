from discord.ext import commands
import discord
import re
from utils.functions import TWAPI_REQUEST
from utils import settings
import traceback
import requests

class Users:
    def __init__(self, bot):
        self.bot = bot
        self.regex = re.compile('^\w+$')

    @commands.command(pass_context=True, aliases=["channel"])
    async def user(self, ctx, *, user):
        await ctx.trigger_typing()
        user = user.split('/')[-1]
        if self.regex.match(user) is None:
            return await ctx.send("That doesn't look like a valid Twitch user. You can only include underscores, letters, and numbers.")
        e = discord.Embed(color=discord.Color(0x6441A4))
        # get user info
        r = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + user)
        if r.json().get("data") == [] or r.status_code == 400 or len(r.json()['data']) == 0:
            return await ctx.send("That user doesn't exist. If you entered the user's full profile url, try redoing the command with just their user name.")
        r.raise_for_status()
        r = r.json()["data"][0]
        # get user streaming status
        s = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + user)
        s.raise_for_status()
        s = s.json()["data"]
        # get user follows
        ft = TWAPI_REQUEST("https://api.twitch.tv/helix/users/follows?first=1&to_id=" + r['id'])
        ft.raise_for_status()
        # get user following
        ff = TWAPI_REQUEST("https://api.twitch.tv/helix/users/follows?first=1&from_id=" + r['id'])
        ff.raise_for_status()
        verified = ""
        if r["broadcaster_type"] == "partner":
            verified = " <:twitch_verified:409725750116089876>"
        e.set_author(icon_url=r["profile_image_url"], name=r["display_name"], url="https://twitch.tv/{}".format(r["login"]))
        e.set_thumbnail(url=r["profile_image_url"])
        e.title = r["login"] + verified
        e.description = r["description"]
        e.add_field(name="Followers", value="{:,}".format(ft.json()['total']))
        e.add_field(name="Following", value="{:,}".format(ff.json()['total']))
        e.add_field(inline=False, name="Views", value="{:,}".format(r["view_count"]))
        if not s == []:
            s = s[0]
            g = TWAPI_REQUEST("https://api.twitch.tv/helix/games?id=" + s["game_id"])
            g.raise_for_status()
            try:
                g = g.json()["data"][0]
            except:
                g = {"name": "Unknown"}
            e.add_field(inline=False, name="Currently Live", value="**{}**\nPlaying {} for {} viewers\n\n**[Watch on Twitch](https://twitch.tv/{})**".format(s['title'], g["name"], s["viewer_count"], user))
            e.set_image(url=s['thumbnail_url'].format(width=1920, height=1080))
        else:
            e.add_field(inline=False, name="Currently Offline", value="[View Twitch Profile](https://twitch.tv/{})".format(user))
            e.set_image(url=r['offline_image_url'])
        await ctx.send(embed=e)

    @commands.command()
    async def connections(self, ctx, *, user: discord.User = None):
        await ctx.trigger_typing()
        if user is None:
            user = ctx.author
        r = requests.get("http://dash.twitchbot.io/api/connections/{}".format(user.id), headers={"Authorization": settings.DASHBOARD})
        if r.status_code == 404:
            return await ctx.send(embed=discord.Embed(description="This user hasn't visited the [TwitchBot dashboard](http://dash.twitchbot.io).", color=discord.Color.red()))
        r.raise_for_status()
        e = discord.Embed(color=discord.Color(0x6441A4))
        e.set_author(icon_url=user.avatar_url or user.default_avatar_url, name="Connections for {}".format(str(user)))
        r = r.json()
        if r['twitch'] == None or r.get('twitch', {'visibility': 0})['visibility'] == 0:
            e.add_field(name="Twitch", value="Not connected", inline=False)
        else:
            e.add_field(name="Twitch", value="Connected to {}".format(r['twitch']['name']), inline=False)
        if r['streamlabs'] == None:
            e.add_field(name="Streamlabs", value="Not connected", inline=False)
        else:
            e.add_field(name="Streamlabs", value="Connected to {}".format(r['streamlabs']['streamlabs']['display_name']), inline=False)
        e.set_footer(text="dash.twitchbot.io")
        await ctx.send(embed=e)

def setup(bot):
    bot.add_cog(Users(bot))
