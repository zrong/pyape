"""
pyape.app
----------------------

app 初始化。
"""

import logging

from pyape.config import GlobalConfig
from pyape.cache import GlobalCache
from pyape.application import PyapeDB, PyapeRedis, PyapeApp

gapp: PyapeApp = None
""" 进程唯一的 PyapeApp 实例。"""

gconf: GlobalConfig = None
""" 全局配置对象。 pyape.config.GlobalConfig 的实例。"""

gdb: PyapeDB = None
""" 全局的数据库引用，PyapeDB 的实例。"""

grc: PyapeRedis = None
""" grc 就是 Global Redis Client 的缩写，PyapeRedis 的实例。"""

gcache: GlobalCache = None
""" 全局缓存实例，pyape.cache.GlobalCache 的实例。"""

logger: logging.Logger = None
""" 全局 logger 对象。"""
