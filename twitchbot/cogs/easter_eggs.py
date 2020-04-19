import math
import random

from discord.ext import commands
from .. import TwitchBot


class EasterEggs(commands.Cog):
    def __init__(self, bot: TwitchBot):
        self.bot = bot
        self.hyperpog = '<:hyperpog:698027337991847987>'
        self.notpog = '<:notpog:698026876505161779>'
        self.pogchamp = '<:PogChamp:586004778304274445>'
        self.weirdchamp = '<:WeirdChamp:605783136907034626>'

    @commands.command()
    async def pogscale(self, ctx: commands.Context):
        # determines the pog-ness
        rand = random.randint(1, 10)

        if ctx.author.id == 188403747049701376 and ctx.channel.id == 283373885120970752:
            rand = 0

        if rand == 0:
            pog = self.notpog + '-'*15 + '|' + '-'*15 + '|'
        elif rand == 5:
            pog = '|' + '-'*14 + ' ' + self.pogchamp + ' ' + '-'*14 + '|'
        elif rand == 10:
            pog = '|' + '-'*15 + '|' + '-'*15 + self.hyperpog
        elif rand < 5:
            before_space = math.floor(((rand / 5) * 11) - 1)
            pog = '|' + '-'*before_space + self.weirdchamp + '-'*(11-before_space) + '|' + '-'*15 + '|'
        elif rand > 5:
            before_space = math.floor((((rand - 5) / 5) * 11) - 1)
            pog = '|' + '-'*15 + '|' + '-'*before_space + self.pogchamp + '-'*(11-before_space) + '|'
        else:
            pog = 'error'

        await ctx.send(
            '**THE POG SCALE:**\n'
            '\n'
            '0                      5                       10\n'
            f'{pog}\n'
            'Not                                          Very\n'
            'Pog                                           Pog\n')


def setup(bot: TwitchBot):
    bot.add_cog(EasterEggs(bot))
