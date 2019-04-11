from colorama import Fore, Back, Style
from colorama import init as color_init
from os import name as os_name
import time
import logging

def GetBotUptime(u):
    t = time.time() - u
    st = time.gmtime(t)
    return "{1} days, {0.tm_hour} hours, and {0.tm_min} minutes".format(st, st.tm_mday - 1)

def SplitIterable(length, iterable):
    items = []
    current_item = {}
    if len(iterable) < length + 1:
        return [iterable]
    for i in iterable.keys():
        if len(current_item) > length - 1:
            items.append(current_item)
            current_item = {}
        current_item[i] = iterable[i]
    if current_item != {}:
        items.append(current_item)
    return items

def FormatOWAPIUser(username):
    u = username.replace("#", "-").replace(" ", "_")
    """fmt = ""
    for let in u:
        for l in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_-":
            if let in l:
                fmt += let
    return fmt"""
    return u

def ReplaceAllInStr(text, dic):
    for i, j in dic.items():
        text = text.replace(str(i), str(j))
    return text

def CheckMultiplePerms(permissions, *args):
    for arg in args:
        if not getattr(permissions, arg):
            return arg.replace("_", " ").capitalize()
    return True

class LogFilter(logging.Filter):
    def filter(self, record):
        return not "unknown event" in record.msg.lower()

class ColorFormatter(logging.Formatter):
    def __init__(self, fmt, datefmt=None):
        super().__init__(fmt, datefmt)
        self.levels = {
            "DEBUG": "VERB",
            "INFO": f"{Back.BLUE+Fore.WHITE}INFO{Style.RESET_ALL}",
            "WARNING": f"{Back.YELLOW+Fore.BLACK}WARN{Style.RESET_ALL}",
            "ERROR": f"{Back.RED+Fore.WHITE}ERR!{Style.RESET_ALL}",
            "CRITICAL": f"{Back.RED+Fore.WHITE}ERR!{Style.RESET_ALL}",
        }

    def format(self, record):
        lv = record.levelname
        record.levelname = self.levels.get(lv, lv)
        return super().format(record)

def initColoredLogging():
    if os_name == 'nt':
        color_init(autoreset=True)
    stream = logging.StreamHandler()
    stream.setFormatter(ColorFormatter(
        f"%(levelname)s {Style.RESET_ALL+Style.DIM}%(name)s @ %(asctime)s{Style.RESET_ALL} >> %(message)s",
        datefmt='%H:%M.%S'
    ))
    return stream
