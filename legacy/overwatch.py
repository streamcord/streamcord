@commands.command(aliases=['ow'])
@commands.cooldown(rate=1, per=2)
async def overwatch(self, ctx, platform, *, username):
    msgs = await lang.get_lang(ctx)
    username = FormatOWAPIUser(username)
    if platform == "pc" and not "-" in username:
        return await ctx.send(msgs['games']['invalid_battletag'])
    elif not platform in ["pc", "psn", "xbl"]:
        return await ctx.send(msgs['games']['invalid_platform'])
    async with ctx.channel.typing():
        r = http.Games.OverwatchAPIRequest(f"/u/{username}/stats?platform={platform}")
    rjson = r.json()
    stats = rjson.get('any') or rjson.get('us') or rjson.get('eu') or rjson.get('kr')
    if r.status_code == 404 or stats is None:
        return await ctx.send(msgs['games']['no_stats_overwatch'])
    elif r.status_code != 200:
        return await ctx.send(f"{msgs['games']['generic_error']} {r.status_code}")
    stats = stats['stats']['competitive']
    e = discord.Embed(color=0x2196F3, title="Overwatch Stats (Competitive)")
    e.set_footer(text=msgs['games']['powered_by_overwatch'])
    e.set_author(
        name=username.replace('-', '#').replace('_', ' '),
        url=f"https://playoverwatch.com/en-us/career/{platform}/{username}",
        icon_url=stats['overall_stats']['avatar']
    )
    e.set_thumbnail(
        url=stats['overall_stats']['avatar']
    )
    e.description = f"{round(stats['game_stats']['time_played'])} total hours played"
    e.add_field(
        name="Competitive Rank",
        value=f"{self.emoji[stats['overall_stats']['tier']]} {stats['overall_stats']['comprank']}"
    )
    e.add_field(
        name="Level",
        value=str(((stats['overall_stats']['prestige'] or 0)*100) + stats['overall_stats']['level'])
    )
    e.add_field(
        name="Stats",
        value=textwrap.dedent(f"""\
        • {stats['game_stats']['damage_done']} damage dealt
          most in game: {stats['game_stats']['all_damage_done_most_in_game']}
        • {stats['game_stats']['healing_done']} healing given
          most in game: {stats['game_stats']['healing_done_most_in_game']}
        • {stats['game_stats']['offensive_assists']} offensive assists
          most in game: {stats['game_stats']['offensive_assists_most_in_game']}
        • {stats['game_stats']['defensive_assists']} defensive assists
          most in game: {stats['game_stats']['defensive_assists_most_in_game']}
        """)
    )
    e.add_field(
        name="Matches Played",
        value=textwrap.dedent(f"""\
        • {stats['game_stats']['games_played']} total
        • {stats['game_stats']['games_won']} wins ({round(stats['game_stats']['games_won']/stats['game_stats']['games_played']*100)}%)
        • {stats['game_stats']['games_tied']} ties
        • {stats['game_stats']['games_lost']} losses
        • {stats['game_stats']['cards']} end-of-match cards
        """)
    )
    e.add_field(
        name="Kills/Deaths",
        value=textwrap.dedent(f"""\
        • {stats['game_stats']['eliminations']} kills
          most in game: {stats['game_stats']['eliminations_most_in_game']}
          env kills: {stats['game_stats']['environmental_kills']}
        • {stats['game_stats']['deaths']} deaths
        • {stats['game_stats']['kpd']} kills per death
        """)
    )
    e.add_field(
        name="Medals",
        value=textwrap.dedent(f"""\
        • {stats['game_stats']['medals']} total
        • {stats['game_stats']['medals_gold']} gold
        • {stats['game_stats']['medals_silver']} silver
        • {stats['game_stats']['medals_bronze']} bronze
        """)
    )
    await ctx.send(embed=e)
