from discord.ext import commands
from functools import wraps
from os import getenv
from motor import motor_asyncio as motor

# this code is currently unused


def uses_mongo():
    def wrapper(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            print(f'in uses_mongo {func.__name__}')
            ctx = args[1]
            ctx.mongo = motor.AsyncIOMotorClient(getenv('MONGO_ADDR'))
            ctx.db = ctx.mongo[getenv('MONGO_DB')]
            res = await func(*args, **kwargs)
            ctx.mongo.close()
            return res
        return wrapped
    return wrapper


class ExtendedContext(commands.Context):
    mongo: motor.AsyncIOMotorClient
    db: motor.AsyncIOMotorDatabase
