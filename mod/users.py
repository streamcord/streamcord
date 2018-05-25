from discord.ext import commands
import discord
from utils.functions import TWAPI_REQUEST
import traceback

class Users:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, aliases=["channel"])
    async def user(self, ctx, *, user):
        await ctx.trigger_typing()
        user = user.split('/')[-1]
        e = discord.Embed(color=discord.Color(0x6441A4))
        r = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + user)
        if r.json()["data"] == [] or r.status_code == 400:
            await ctx.send("That user doesn't exist. If you entered the user's full profile url, try redoing the command with just their user name.")
        r.raise_for_status()
        r = r.json()["data"][0]
        s = TWAPI_REQUEST("https://api.twitch.tv/helix/streams?user_login=" + user)
        s.raise_for_status()
        s = s.json()["data"]
        verified = ""
        if not r["broadcaster_type"] == "":
            verified = " <:twitch_verified:409725750116089876>"
        e.set_author(icon_url=r["profile_image_url"], name=r["display_name"], url="https://twitch.tv/{}".format(r["login"]))
        e.set_thumbnail(url=r["profile_image_url"])
        e.title = r["login"] + verified
        e.description = r["description"]
        e.add_field(inline=False, name="Views", value=r["view_count"])
        if not s == []:
            s = s[0]
            g = TWAPI_REQUEST("https://api.twitch.tv/helix/games?id=" + s["game_id"])
            g.raise_for_status()
            g = g.json()["data"][0]
            e.add_field(inline=False, name="Currently Live", value="Playing {} for {} viewers\n\n**[Watch on Twitch](https://twitch.tv/{})**".format(g["name"], s["viewer_count"], user))
        else:
            e.add_field(inline=False, name="Currently Offline", value="[View Twitch Profile](https://twitch.tv/{})".format(user))
        await ctx.send(embed=e)

def setup(bot):
    bot.add_cog(Users(bot))
