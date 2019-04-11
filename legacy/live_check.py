class LiveCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(no_pm=True, aliases=['live_check'])
    async def live_role(self, ctx):
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            await ctx.send(embed=lang.EmbedBuilder(msgs['live_role']['command_usage']))

    @live_role.command()
    async def set(self, ctx, *, role: typing.Union[discord.Role, str] = None):
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        elif not ctx.guild.me.permissions_in(ctx.channel).manage_roles:
            return await ctx.send(msgs['permissions']['bot_need_perm'].format(permission="Manage Roles"))
        if role is None:
            return await ctx.send(msgs['live_role']['no_role_mentioned'])
        if type(role) == str:
            role = discord.utils.find(lambda m: role.lower() in m.name.lower(), ctx.guild.roles)
            if role is None:
                return await ctx.send(msgs['live_role']['role_not_found'])
        r.table('live_role').insert({"id": str(ctx.guild.id), "role": str(role.id)}, conflict="update").run(self.bot.rethink, durability="soft", noreply=True)
        await ctx.send(msgs['live_role']['add_success'].format(role=role.name))
        cursor = r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink, durability="soft")
        if cursor is None:
            return # db hasn't updated yet
        g = ctx.guild
        try:
            filt = cursor.get('filter')
            lc = int(cursor['role'])
            role = discord.utils.find(lambda r: r.id == int(lc), g.roles)
            for m in filter(lambda m: isinstance(m.activity, discord.Streaming), g.members):
                if not m.bot:
                    if filt is not None:
                        frole = discord.utils.get(g.roles, id=int(filt))
                        if not frole.id in map(lambda r: r.id, m.roles):
                            continue
                    log.info("Adding streamer role to {before.id} in {before.guild.id}".format(before=m))
                    await m.add_roles(role, reason="User went live on Twitch")
        except discord.Forbidden as e:
            await ctx.send(msgs['live_role']['missing_perms_ext'])

    @live_role.command(name="filter", no_pm=True)
    async def _filter(self, ctx, *, role: typing.Union[discord.Role, str] = None):
        """Restricts Live Role to users with a specific role"""
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        elif not ctx.guild.me.permissions_in(ctx.channel).manage_roles:
            return await ctx.send(msgs['permissions']['bot_need_perm'].format(permission="Manage Roles"))
        if role is None:
            return await ctx.send(msgs['live_role']['no_role_mentioned'])
        if type(role) == str:
            role = discord.utils.find(lambda m: role.lower() in m.name.lower(), ctx.guild.roles)
            if role is None:
                return await ctx.send(msgs['live_role']['role_not_found'])
        cursor = r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink, durability="soft")
        if cursor is None:
            return await ctx.send(msgs['live_role']['not_set_up'])
        r.table('live_role').insert({"id": str(ctx.guild.id), "filter": str(role.id)}, conflict="update").run(self.bot.rethink, durability="soft", noreply=True)
        await ctx.send(msgs['live_role']['filter_success'])
        g = ctx.guild
        filt = role.id
        lc = int(cursor['role'])
        role = discord.utils.find(lambda r: str(r.id) == str(lc), g.roles)
        for m in filter(lambda m: role.id in map(lambda r: r.id, m.roles), g.members):
            if filt is not None:
                frole = discord.utils.get(g.roles, id=int(filt))
                if not frole.id in map(lambda r: r.id, m.roles):
                    log.info("Removing streamer role from {before.id} in {before.guild.id}".format(before=m))
                    await m.remove_roles(role, reason="User does not have filter role for Live Role")

    @live_role.command(aliases=['del', 'remove'])
    async def delete(self, ctx):
        msgs = await lang.get_lang(ctx)
        if not ctx.author.permissions_in(ctx.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        try:
            cursor = r.table('live_role').get(str(ctx.guild.id))
            if cursor.run(self.bot.rethink, durability="soft") is None:
                return await ctx.send(msgs['live_role']['not_set_up'])
            cursor.delete().run(self.bot.rethink, durability="soft", noreply=True)
        except KeyError as e:
            return await ctx.send(msgs['live_role']['not_set_up'])
        except:
            raise
        else:
            return await ctx.send(msgs['live_role']['del_success'])

    @live_role.command(aliases=['list'])
    async def view(self, ctx):
        msgs = await lang.get_lang(ctx)
        cursor = r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink, durability="soft")
        if cursor is None:
            return await ctx.send(msgs['live_role']['not_set_up'])
        role = discord.utils.find(lambda n: n.id == int(cursor['role']), ctx.guild.roles)
        await ctx.send(msgs['live_role']['view_response'].format(role=role.name))

    @live_role.command()
    async def check(self, ctx):
        try:
            msgs = await lang.get_lang(ctx)
            cursor = r.table('live_role').get(str(ctx.guild.id)).run(self.bot.rethink, durability="soft")
            if cursor is None:
                return await ctx.send(msgs['live_role']['not_set_up'])
            try:
                role = ctx.guild.get_role(int(cursor['role']))
                if cursor.get('filter') is not None:
                    cursor['filter'] = ctx.guild.get_role(int(cursor['filter']))
            except TypeError:
                return await ctx.send(msgs['live_role']['not_set_up'])
            e = discord.Embed(color=0x6441A4, title="Live Role Check")
            live_members = len(list(filter(lambda m: isinstance(m.activity, discord.Streaming) and not m.bot, ctx.guild.members)))
            members_with_lr = len(list(filter(lambda m: role in m.roles, ctx.guild.members)))
            status = "<:tickYes:342738345673228290>"
            if live_members != members_with_lr:
                status = "<:tickNo:342738745092734976>"
            e.description = textwrap.dedent(f"""\
            Live role: {role.name}
            Filter: {str(cursor.get('filter'))}

            {live_members} members in server that are streaming
            {members_with_lr} members with the server's live role

            **Live role status: {status}**
            """)
            e.set_footer(text="Note: This command will not work properly if a filter role has been set")
            await ctx.send(embed=e)
        except:
            await ctx.send(traceback.format_exc())

@bot.event
async def on_member_update(before, after):
    if before.guild is None or before.bot:
        return
    elif not hasattr(bot, 'live_role'):
        logging.warn('Bot hasn\'t feteched live_role data yet')
        return
    was_streaming = isinstance(before.activity, discord.Streaming)
    is_streaming = isinstance(after.activity, discord.Streaming)
    if was_streaming == is_streaming:
        return
    try:
        live_role = list(filter(lambda r: int(r['id']) == before.guild.id, bot.live_role))
    except ValueError:
        return
    if len(live_role) == 0:
        return
    live_role = live_role[0]
    if live_role['role'] is None:
        return
    role = discord.Object(id=int(live_role['role']))
    logging.info(f'Updating live role for {before.id} in {before.guild.id}: {was_streaming} -> {is_streaming}')
    try:
        if (not was_streaming) and is_streaming: # user went live
            if live_role.get('filter') is not None:
                if discord.utils.get(after.roles, id=int(live_role['filter'])) is None:
                    return # user doesn't have filter role
            await after.add_roles(role, reason="User went live on Twitch")
        elif was_streaming and (not is_streaming):
            await after.remove_roles(role, reason="User no longer live on Twitch")
    except discord.Forbidden:
        logging.info(f'Live role forbidden for {before.id} in {before.guild.id}')

async def update_live_role_cache(bot):
    _nonce = secrets.token_urlsafe(5)
    bot._lr_nonce = _nonce
    while True:
        if not bot._lr_nonce == _nonce:
            logging.info('preventing duplicate live role cache update')
            return
        logging.info('Updating live role cache')
        bot.live_role = list(r.table('live_role').run(bot.rethink, durability="soft"))
        await asyncio.sleep(30)
