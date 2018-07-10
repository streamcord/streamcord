import discord, asyncio, logging

logging.basicConfig(level=logging.INFO)
c = discord.Client()

async def loop():
    await c.wait_until_ready()
    while not c.is_closed():
        await c.change_presence(activity=discord.Streaming(name="testing", url="https://twitch.tv/kraken"))
        await asyncio.sleep(10)
        await c.change_presence(activity=discord.Game(name="oof"))
        await asyncio.sleep(10)

c.loop.create_task(loop())
c.run("MjE4NDcwNDYzNjkxNjg1ODkw.De8DYA.dvKYe7l7TKgJow7Tj0CP1mMK3J8", bot=False)
