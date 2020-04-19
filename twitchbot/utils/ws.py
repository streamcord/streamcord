from os import getenv
from threading import Thread
import asyncio
import logging
from flask import Flask, jsonify, abort, request


class ThreadedWebServer:
    def __init__(self, bot):
        self.app = Flask(__name__)
        self.bot = bot
        self.log = logging.getLogger("utils.ws")
        self.thread = None

        # 4000 = pro bot, so offset for 1
        if getenv('ENABLE_PRO_FEATURES') == '1':
            self.flask_port = 4000
        else:
            self.flask_port = 4001 + bot.cluster_index

    def run(self):
        app = self.app
        bot = self.bot

        @app.before_request
        def before_request():
            if request.headers.get("Authorization") != getenv('DASHBOARD_KEY'):
                return abort(401)

        @app.errorhandler(401)
        def unauthorized(*args, **kwargs):
            return jsonify(code=401, error="Authorization required"), 401

        @app.errorhandler(404)
        def not_found(*args, **kwargs):
            return jsonify(code=404, error="Endpoint not found"), 404

        @app.route('/guilds/<gid>')
        def get_guild(gid):
            guild = bot.get_guild(int(gid))
            if guild is None:
                try:
                    guild = asyncio.get_event_loop() \
                        .run_until_complete(bot.fetch_guild(int(gid)))
                    if guild is None:
                        return jsonify(error="Guild not found"), 404
                except Exception as e:
                    return jsonify(error=f"Guild not found: {e}"), 404
            elif guild.unavailable:
                return jsonify(unavailable=True), 502

            g_channels = [{
                "name": c.name,
                "id": str(c.id),
                "position": c.position,
                "type": type(c).__name__,
                } for c in guild.channels]
            g_roles = [{
                "name": r.name,
                "id": str(r.id),
                "position": r.position,
                "mentionable": r.mentionable,
                "managed": r.managed
                } for r in guild.roles]

            return jsonify(
                name=guild.name,
                icon=guild.icon,
                channels=g_channels,
                roles=g_roles,
                region=str(guild.region),
                locale=getattr(guild, 'preferred_locale', 'en'))

        @app.route('/channels/<cid>')
        def get_channel(cid):
            channel = bot.get_channel(int(cid))
            if channel is None:
                return abort(404)

            return jsonify(
                guild_id=str(channel.guild.id))

        self.log.info('Starting Flask on port %i', self.flask_port)
        try:
            app.run(host='0.0.0.0', port=self.flask_port)
        except Exception:
            self.log.exception("Failed to start web server")

    def keep_alive(self):
        t = Thread(target=self.run, daemon=True)
        t.start()
        self.thread = t
        return t
