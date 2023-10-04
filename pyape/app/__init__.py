"""
pyape.app
----------------------

所有位于 pyape.app 包中的内容，都可能会引用下面的 6 个全局变量中的一个或多个。
所有引用了下面任何全局变量的代码，都应该放在 pyape.app 包中。
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
