from utils import settings
from discord.ext import commands
import discord, asyncio
import socketio
import json
import logging

class Streamlabs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sio = socketio.AsyncClient()
        bot.loop.create_task(self.manage_connections())

    async def websocket_connect(self, token):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(538842013676601364)

        @self.sio.on('connect')
        async def on_connect():
            logging.info('Connected to wss://sockets.streamlabs.com')
            await channel.send("Connected to wss://sockets.streamlabs.com")

        @self.sio.on('event')
        async def on_event(data):
            if not data.get('for') in ('twitch_account', 'streamlabs'):
                return
            if data['type'] == 'follow':
                for new in data['message']:
                    await channel.send(f"{new['name']} is now following!")
            elif data['type'] == 'subscription':
                for new in data['message']:
                    await channel.send(f"{new['name']} just subscribed for {new['months']} month(s)!")
            elif data['type'] == 'bits':
                for new in data['message']:
                    await channel.send(f"{new['name']} just cheered {new['amount']} bits!\n{new['message']}")
            elif data['type'] == 'donation':
                for new in data['message']:
                    await channel.send(f"{new['name']} just donated {new['formatted_amount']}!\n{new['message']}")
            else:
                await channel.send("Incoming streamlabs socket data:\n" + str(data)[:1900])

        @self.sio.on('disconnect')
        async def on_disconnect():
            await channel.send('Disconnected from socket.io server')

        await self.sio.connect(f'wss://sockets.streamlabs.com?token={token}', transports=['websocket'])

    async def manage_connections(self):
        token = ""
        await self.websocket_connect(token)

def setup(bot):
    #bot.add_cog(Streamlabs(bot))
