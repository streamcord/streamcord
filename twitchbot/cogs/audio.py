import discord
import wavelink

from discord.ext import commands
from os import getenv
from secrets import token_hex
from urllib.parse import urlparse
from ..utils import lang


class Audio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if not hasattr(bot, 'wavelink'):
            self.bot.wavelink = wavelink.Client(self.bot)

        self.bot.loop.create_task(self.start_nodes())
        self.voice_states = {}

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        await self.bot.wavelink.initiate_node(
            host=getenv('LAVALINK_HOST'),
            port=int(getenv('LAVALINK_PORT')),
            rest_uri=f'http://{getenv("LAVALINK_HOST")}:{getenv("LAVALINK_PORT")}/',
            password=getenv('LAVALINK_PASS'),
            identifier=f'cluster-{self.bot.cluster_index}-{token_hex(5)}',
            region='us_central'
        )

    @commands.command(no_pm=True, aliases=["join"])
    async def _connect(self, ctx, *, channel: discord.VoiceChannel = None):
        msgs = await lang.get_lang(ctx)

        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                return await ctx.send(
                    msgs['audio']['author_not_in_voice_channel']
                )

        player = self.bot.wavelink.get_player(ctx.guild.id)
        await player.connect(channel.id)

    @commands.command(no_pm=True, aliases=["listen"])
    async def play(self, ctx, *, query):
        msgs = await lang.get_lang(ctx)

        url = urlparse(query)
        query = "https://twitch.tv/" + url.path.strip("/")
        tracks = await self.bot.wavelink.get_tracks(query)
        if not tracks:
            return await ctx.send(
                msgs['audio']['user_does_not_exist_or_not_streaming']
            )

        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.is_connected:
            await ctx.invoke(self._connect)

        await player.set_volume(100)
        await player.play(tracks[0])
        self.voice_states[ctx.guild.id] = tracks[0]
        await ctx.invoke(self.nowplaying)

    @commands.command(no_pm=True, aliases=["stop", "disconnect", "dc"])
    async def leave(self, ctx):
        msgs = await lang.get_lang(ctx)

        player = self.bot.wavelink.get_player(ctx.guild.id)
        await player.disconnect()
        self.voice_states.pop(ctx.guild.id, None)
        try:
            await ctx.message.guild.voice_client.disconnect()
        except AttributeError:
            pass
        await ctx.send(msgs['audio']['disconnected'])

    @commands.command(no_pm=True, aliases=["np", "playing"])
    async def nowplaying(self, ctx):
        msgs = await lang.get_lang(ctx)

        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.is_connected:
            return await ctx.send(msgs['audio']['not_streaming'])

        voice_state = self.voice_states.get(ctx.guild.id)
        if voice_state is None:
            return await ctx.send(msgs['audio']['not_streaming'])

        e = discord.Embed(
            color=0x6441A4,
            title=msgs['audio']['now_playing']['title']
            .format(channel=ctx.author.voice.channel),
            description=f"{voice_state.title}\n{voice_state.uri}"
        )
        e.set_footer(
            icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url,
            text=f"{ctx.author} - {msgs['audio']['now_playing']['footer']}"
        )

        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(Audio(bot))
