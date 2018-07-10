from discord.ext import commands
import discord
import math
import traceback
import datetime, time
from utils.functions import DBOTS_REQUEST

# 500 bits = 1 tier

class Bits:
    def __init__(self, bot):
        self.bot = bot
        self.emoji = {
            "tier1": "<a:bit_1:458259468568756235>",
            "tier2": "<a:bit_2:458259469256622091>",
            "tier3": "<a:bit_3:458259470116454410>",
            "tier4": "<a:bit_4:458259470150008832>",
            "tier5": "<a:bit_5:458259470502330378>"
        }

    @commands.command()
    async def bits(self, ctx, *, user: discord.User = None):
        try:
            if user is None:
                user = ctx.author
            bits = self.bot.bits.get(str(user.id))
            if bits is None:
                return await ctx.send("That user hasn't sent any messages, so I haven't created an account for them.")
            e = discord.Embed(color=discord.Color(0x6441A4))
            e.set_author(icon_url=user.avatar_url or user.default_avatar_url, name="Bits for {0.name}#{0.discriminator}".format(user))
            e.set_thumbnail(url=user.avatar_url or user.default_avatar_url)
            e.add_field(name="Bits", value=str(bits['bits']))
            tier = math.ceil(bits['bits'] / 500)
            progress = bits['bits'] / (500 * tier)
            emoji = self.emoji.get("tier" + str(tier))
            if tier < 1:
                emoji = self.emoji['tier1']
            elif tier > 5:
                emoji = self.emoji['tier5']
            e.add_field(name="Tier", value="{} ({})".format(emoji, tier))
            e.add_field(name="Progress to next tier", value="{}% ({} bits left)".format(round(progress*100, 1), 500 - (bits['bits'] % 500)))
            e.add_field(name="Multiplier", value="{}x ({} redeemed votes)".format(bits['multiplier'], bits['votes']))
            e.set_footer(text="Type 'twitch redeem' to redeem rewards. Multipliers are only active 24 hours after you redeem them.")
            e.timestamp = datetime.datetime.now()
            await ctx.send(embed=e)
        except:
            await ctx.send(traceback.format_exc())

    @commands.command()
    @commands.cooldown(per=60, rate=1, type=commands.BucketType.user)
    async def redeem(self, ctx):
        ts = self.bot.bits[str(ctx.author.id)]['multiplier_nonce']
        if ts + 86400 > time.time():
            return await ctx.send("You already redeemed your multiplier {0.tm_hour} hours and {0.tm_min} minutes ago. You can still use it for 24 hours".format(time.gmtime(time.time() - ts)))
        r = DBOTS_REQUEST("/bots/375805687529209857/check?userId=" + str(ctx.author.id))
        r.raise_for_status()
        if r.json()['voted'] == 1:
            self.bot.bits[str(ctx.author.id)]['multiplier'] += 0.1
            self.bot.bits[str(ctx.author.id)]['multiplier_nonce'] = time.time()
            self.bot.bits[str(ctx.author.id)]['votes'] += 1
            return await ctx.send("Thanks for upvoting! Your bit multiplier has been increased to {} is now active for 24 hours.".format(self.bot.bits[str(ctx.author.id)]['multiplier']))
        return await ctx.send("You need to upvote first to redeem your multiplier! Go to <https://discordbots.org/bot/twitch/vote> and press 'vote for this bot'.")

def setup(bot):
    bot.add_cog(Bits(bot))
