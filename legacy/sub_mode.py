class Guild(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(no_pm=True)
    async def sub_mode(self, ctx):
        if not settings.UseBetaBot:
            return
        if ctx.invoked_subcommand is None:
            msgs = await lang.get_lang(ctx)
            return await ctx.send(msgs['guild']['submode']['command_usage'])

    @sub_mode.command()
    async def on(self, ctx, *, flags=""):
        """Sets the subscriber-only mode to only allow subscribers to join the server.
        Requires the 'Manage Server' permission.

        Possible flags:
        --use-server-owner  : Check the server owner for Twitch channel connections instead of the message author.
        --user-id=(id here) : Check a specific user for Twitch channel connections instead of the message author.
        """
        msgs = await lang.get_lang(ctx)
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        elif not ctx.guild.me.permissions_in(ctx.message.channel).kick_members:
            return await ctx.send(msgs['permissions']['bot_need_perm'].format(permission="Kick Members"))
        flags = flags.split(" ")
        user = ctx.author
        if "--use-server-owner" in flags:
            user = ctx.guild.owner
        potential_users = list(filter(lambda f: f.startswith("--user-id="), flags))
        if len(potential_users) > 0:
            user = ctx.guild.get_member(int(potential_users[0].split('=')[1]))
        if user is None:
            return await ctx.send(msgs['guild']['user_not_in_guild'])
        r = requests.get("https://dash.twitchbot.io/api/connections/{}".format(user.id), headers={"X-Access-Token": settings.DashboardKey})
        if r.status_code == 404:
            return await ctx.send(msgs['guild']['no_login_dash'].format(user=user.username))
        elif r.status_code > 299:
            return await ctx.send(msgs['guild']['dash_http_error'].format(error=r.status_code))
        if r.json().get('twitch') is None:
            return await ctx.send(msgs['guild']['no_link_dash'].format(user=user.username))
        opts = db.table('guild_config')
        tw_data = {"auth": r.json()['twitch']['auth_info'], "login": r.json()['twitch']['login'], "id": r.json()['twitch']['id']}
        payload = {
            "id": ctx.guild.id,
            "sub_link": {"user": user.id, "twitch": tw_data, "mode": "join"}
        }
        opts.upsert(payload, tinydb.Query().id == str(ctx.guild.id))
        return await ctx.send(msgs['guild']['submpde']['enabled_success'].format(channel=r.json()['twitch']['login']))

    @sub_mode.command()
    async def off(self, ctx):
        """Turns off subscriber-only mode for the current server.
        Requires the 'Manage Server' permission.
        """
        msgs = await lang.get_lang(ctx)
        if not ctx.message.author.permissions_in(ctx.message.channel).manage_guild:
            return await ctx.send(msgs['permissions']['user_need_perm'].format(permission="Manage Server"))
        opts = db.table('guild_config')
        opts.update(delete('sub_link'), tinydb.Query().id == ctx.guild.id)
        return await ctx.send(msgs['guild']['submode']['disable_success'])

def setup(bot):
    #bot.add_cog(Guild(bot))

    #@bot.event
    async def on_member_join(member):
        msgs = await lang.get_lang(lang.FakeCtxObject(bot, member))
        opts = db.table('guild_config')
        g = opts.get(tinydb.Query().id == str(member.guild.id))
        if g is None or g.get('sub_link') is None:
            return
        g = g['sub_link']
        check_id = None
        async with aiohttp.ClientSession() as session:
            async with session.get('https://dash.twitchbot.io/api/connections/{}'.format(member.id), headers={"X-Access-Token": settings.DashboardKey}) as r:
                response = await r.json()
                if r.status == 404:
                    logging.info('user didn\'t log into dash')
                    try:
                        ch = member.dm_channel
                        if ch is None:
                            await member.create_dm()
                            ch = member.dm_channel
                        await ch.send(msgs['guild']['submode']['kick_message'].format(g['twitch']['login']))
                    except:
                        logging.info('didn\'t send kick message to user:\n{}'.format(traceback.format_exc()))
                    return await member.kick(reason=msgs['guild']['submode']['kick_audit_log'])
                elif r.status > 299:
                    logging.error('Failed to get info from dashboard:\n{}'.format(str(response)))
                    return
                check_id = response.get('twitch', {}).get('id')
                if check_id is None:
                    logging.info('user didn\'t connect twitch')
                    try:
                        ch = member.dm_channel
                        if ch is None:
                            await member.create_dm()
                            ch = member.dm_channel
                        await ch.send(msgs['guild']['submode']['kick_message'].format(g['twitch']['login']))
                    except:
                        logging.info('didn\'t send kick message to user:\n{}'.format(traceback.format_exc()))
                    return await member.kick(reasonmsgs['guild']['submode']['kick_audit_log'])
            r = await http.oAuth.TwitchAPIOAuthRequest('https://api.twitch.tv/kraken/channels/{}/subscriptions/{}'.format(g['twitch']['login'], check_id), response['twitch']['auth_info'], response['twitch']['id'])
            if r.status == 404:
                logging.info('twapi determined user wasn\'t a sub')
                try:
                    ch = member.dm_channel
                    if ch is None:
                        await member.create_dm()
                        ch = member.dm_channel
                    await ch.send(msgs['guild']['submode']['kick_message'].format(g['twitch']['login']))
                except:
                    logging.info('didn\'t send kick message to user:\n{}'.format(traceback.format_exc()))
                return await member.kick(reason=msgs['guild']['submode']['kick_audit_log'])
            elif r.status > 299:
                logging.error('failed to get sub data from twapi:\n{}'.format(await r.text()))
                return
            # if the user made it through all this then they're a subscriber
            #resp = await r.json()


# http oauth stuff

class oAuth:
    async def NewTwitchOAuthToken(oauthinfo, aio_session, uid, nested=False):
        async with aio_session as session:
            params = {
                "client_id": settings.Twitch.ClientID,
                "client_secret": settings.Twitch.Secret,
                "grant_type": "refresh_token",
                "refresh_token": oauthinfo['refresh_token']
            }
            resp = None
            async with session.post('https://id.twitch.tv/oauth2/token', params=params) as r:
                if r.status > 299:
                    if not nested:
                        await asyncio.sleep(1)
                        return NewTwitchOAuthToken(oauthinfo, aio_session, nested=True)
                    else:
                        raise requests.exceptions.ConnectionError("unable to get access token:\n{}".format(await r.text()))
                resp = await r.json()
                params = {
                    "access_token": resp['access_token'],
                    "refresh_token": resp['refresh_token']
                }
            async with session.post('https://dash.twitchbot.io/api/connections/{}/token'.format(uid), headers={"X-Access-Token": settings.Twitch.ClientID}, params=params):
                if r.status > 299:
                    logging.error('failed to update token info to dashboard ({}):\n{}'.format(r.status, await r.text()))
            return resp

    async def TwitchAPIOAuthRequest(url, oauthinfo, uid, nested=False):
        async with aiohttp.ClientSession() as session:
            headers = {
                "Client-ID": settings.Twitch.ClientID,
                "Authorization": "OAuth " + oauthinfo['access_token']
            }
            async with session.get(url, headers=headers) as r:
                if r.status in [401, 403]:
                    if not nested:
                        code = await NewTwitchOAuthToken(oauthinfo, session, uid)
                        return TwitchAPIOAuthRequest(url, code, uid, nested=True)
                    else:
                        raise requests.exceptions.ConnectionError("failed to get url {} ({}):\n{}".format(r.url, r.status, await r.text()))
                elif r.status > 499:
                    if not nested:
                        return TwitchAPIOAuthRequest(url, oauthinfo, uid, nested=True)
                    else:
                        raise requests.exceptions.ConnectionError("failed to get url {} ({}):\n{}".format(r.url, r.status, await r.text()))
                return r
