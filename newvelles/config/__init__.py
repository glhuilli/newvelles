import configparser
from os import path


def config():
    p = path.dirname(path.abspath(__file__))
    c = configparser.ConfigParser()
    c.read(path.join(p, "newvelles.ini"))
    return c


def debug():
    return config().get("PARAMS", "debug") == "True"
