from discord.ext import commands
import discord
from utils.functions import TWAPI_REQUEST
import traceback

class Users:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True, aliases=["channel"])
    async def user(self, ctx, *, user):
        try:
            await self.bot.send_typing(ctx.message.channel)
            if "https://twitch.tv/" in user:
                user = username.strip("https://twitch.tv").strip("/")
            e = discord.Embed(color=discord.Color(0x6441A4))
            r = TWAPI_REQUEST("https://api.twitch.tv/helix/users?login=" + user)
            r.raise_for_status()
            if r.json()["data"] == []:
                await self.bot.say("That user doesn't exist.")
            else:
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
                await self.bot.say(embed=e)
        except:
            await self.bot.say(traceback.format_exc())

def setup(bot):
    bot.add_cog(Users(bot))
