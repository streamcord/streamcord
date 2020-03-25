from aiofiles.os import wrap
import datadog

from itertools import islice
import logging
from os import getenv
import time


# pylint: disable=too-few-public-methods
class dogstatsd:
    create_event = wrap(datadog.api.Event.create)
    gauge = wrap(datadog.statsd.gauge)
    histogram = wrap(datadog.statsd.histogram)
    increment = wrap(datadog.statsd.increment)


def get_bot_uptime(start_time):
    t = time.gmtime(time.time() - start_time)
    return f"{t.tm_mday - 1} days, {t.tm_hour} hours, and {t.tm_min} minutes"


def split_every(n, iterable):
    i = iter(iterable)
    piece = list(islice(i, n))
    while piece:
        yield piece
        piece = list(islice(i, n))


def replace_multiple(text, dic):
    for i, j in dic.items():
        text = text.replace(str(i), str(j))
    return text


def check_permission_set(permissions, *args):
    for arg in args:
        if not getattr(permissions, arg):
            return arg.replace("_", " ").capitalize()
    return True


def is_canary_bot():
    return getenv('ENABLE_EXPERIMENTS') == '1'


def is_owner(uid):
    return str(uid) in getenv('BOT_OWNERS').split(',')


def is_banned(uid):
    return str(uid) in getenv('BANNED_USERS').split(',')


# pylint: disable=too-few-public-methods
class LogFilter(logging.Filter):
    def filter(self, record):
        return "unknown event" not in record.msg.lower()


class LogFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            '%(levelname)s %(name)s @ %(asctime)s >> %(message)s',
            '%H:%M.%S')
        self.levels = {
            "DEBUG": "VERB",
            "INFO": "INFO",
            "WARNING": "WARN",
            "ERROR": "ERR!",
            "CRITICAL": "ERR!",
        }

    def format(self, record):
        lv = record.levelname
        record.levelname = self.levels.get(lv, lv)
        return super().format(record)

    @staticmethod
    def init_logging():
        stream = logging.StreamHandler()
        stream.setFormatter(LogFormatter())
        return stream
