import asyncio
import discord
import math

class EmbedPaginator:
    def __init__(self, embed: discord.Embed, per_page: int = 10, timeout: int = 90):
        self.embed = embed
        self.per_page = 10
        self.timeout = timeout
        self._message = None
        self._title_format = self.embed.title + " - {} / {}"
        self._current_page = 0
        if type(embed.fields) == discord.Embed.Empty:
            raise ValueError("Embed needs at least one field.")
        self._count = math.ceil(len(embed.fields) / per_page)
        self._pages = [self.embed.fields[x:x+per_page] for x in range(0, len(self.embed.fields), per_page)]

    def _update_page(self, page: int):
        p = self._pages[page]
        self.embed.clear_fields()
        for field in p:
            self.embed.add_field(name=field.name, value=field.value, inline=field.inline)
        self._current_page = page
        self.embed.title = self._title_format.format(self._current_page+1, self._count)

    async def page(self, ctx):
        self._update_page(0)
        message = await ctx.send(embed=self.embed)
        await message.add_reaction("◀")
        await message.add_reaction("❌")
        await message.add_reaction("▶")
        while True:
            try:
                reaction, user = await ctx.bot.wait_for('reaction_add', timeout=self.timeout, check = lambda r, u: r.message.channel == ctx.channel and u == ctx.author and r.message.id == message.id)
                if str(reaction.emoji) == "◀":
                    if self._current_page == 0:
                        pass
                    else:
                        self._update_page(self._current_page - 1)
                        await message.edit(embed=self.embed)
                elif str(reaction.emoji) == "❌":
                    await message.delete()
                    await ctx.message.add_reaction("✅")
                    break
                elif str(reaction.emoji) == "▶":
                    if self._current_page == self._count-1:
                        pass
                    else:
                        self._update_page(self._current_page + 1)
                        await message.edit(embed=self.embed)
                await message.remove_reaction(reaction.emoji, user)
            except asyncio.TimeoutError:
                await message.delete()
                await ctx.message.add_reaction("⏱")
                break
            except:
                raise

class DiscordPaginationExtender:
    def __init__(self, pages, timeout: int = 90):
        self.pages = pages
        self.timeout = timeout
        self._current_page = 0

    async def page(self, ctx):
        message = await ctx.send(self.pages[self._current_page])
        await message.add_reaction("◀")
        await message.add_reaction("❌")
        await message.add_reaction("▶")
        while True:
            try:
                reaction, user = await ctx.bot.wait_for('reaction_add', timeout=self.timeout, check = lambda r, u: r.message.channel == ctx.channel and u == ctx.author and r.message.id == message.id)
                if str(reaction.emoji) == "◀":
                    if self._current_page == 0:
                        pass
                    else:
                        self._current_page -= 1
                        await message.edit(embed=self.pages[self._current_page])
                elif str(reaction.emoji) == "❌":
                    await message.delete()
                    await ctx.message.add_reaction("✅")
                    break
                elif str(reaction.emoji) == "▶":
                    if self._current_page == len(self.pages)-1:
                        pass
                    else:
                        self._current_page += 1
                        await message.edit(embed=self.pages[self._current_page])
                await message.remove_reaction(reaction.emoji, user)
            except asyncio.TimeoutError:
                await message.delete()
                await ctx.message.add_reaction("⏱")
                break
            except:
                raise
