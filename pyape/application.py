"""
pyape.application
----------------------

pyape 框架的核心应用程序。
"""
import sys
import importlib
from typing import TypeVar, Self, Final
from types import ModuleType
from collections.abc import Callable, Sequence
from decimal import Decimal
from datetime import datetime
import logging
import warnings

from sqlalchemy.engine import Row, RowMapping, Result
from redis.client import Redis

from pyape import uwsgiproxy
from pyape.db import SQLAlchemy, DBManager
from pyape.config import GlobalConfig, RegionalConfig, Dicto
from pyape.cache import GlobalCache
from pyape.error import AppError, ErrorCode
from pyape.logging import get_logging_handler, get_pyzog_handler


FrameworkApp = TypeVar('FrameworkApp')
""" 绑定 Flask 或者 FastApi 类型。"""

FrameworkRouter = TypeVar('FrameworkRouter')
""" 绑定 flask.Blueprint 或者 fastapi.APIRouter """

# PDB = TypeVar('PDB', bound='PyapeDB')
# PRedis = TypeVar('PRedis', bound='PyapeRedis')


class CreateArgument(Dicto):
    """保存创建框架 app 时使用的附加 class。"""

    FrameworkAppClass: type = None

    init_app_method: Callable = None
    """ 外部初始化方法，若提供，在初始化后调用。"""


class PyapeApp:
    """Pyape 支持 Flask 和 FastApi，需要一个抽象类作为中间态。"""

    PROJECT_PACKAGE_NAME: Final[str] = 'app'
    """ 位于项目中的提供路由功能的包名。必须为 app。"""

    package_name: str = None
    """ pyape 的包名。一般为 pyape.app.__name__ 的值。"""

    create_arg: CreateArgument = None

    framework_app: FrameworkApp = None
    """ 框架 App 对象。"""

    gconf: GlobalConfig = None
    """ 全局配置对象。 pyape.config.GlobalConfig 的实例。"""

    gdb: 'PyapeDB' = None
    """ 全局的数据库引用，PyapeDB 的实例。"""

    grc: 'PyapeRedis' = None
    """ grc 就是 Global Redis Client 的缩写，PyapeRedis 的实例。"""

    gcache: GlobalCache = None
    """ 全局缓存实例，pyape.cache.GlobalCache 的实例。"""

    logger: logging.Logger = None
    """ 全局 Logger。"""

    def __init__(
        self,
        gconf: GlobalConfig,
        create_arg: CreateArgument = None,
        package_name: str = 'pyape.app',
    ) -> None:
        self.gconf = gconf
        self.create_arg = create_arg
        self.package_name = package_name

        # 必须最先执行配置文件的设置
        self.set_package_global('gconf', self.gconf)

        # 设置自身
        self.set_package_global('gapp', self)

    @property
    def app(self) -> FrameworkApp:
        if self.framework_app:
            return self.framework_app
        raise AppError('No application found.', ErrorCode.APP_NOT_FOUND)

    @property
    def debug(self) -> bool:
        raise NotImplementedError(f'{self.__class__.__name__}.debug')

    def check_package_name(self, global_name: str) -> ModuleType:
        """检查全局模块名称。"""
        mod = sys.modules.get(self.package_name)
        if mod is None:
            raise AppError(
                f'Module {self.package_name} not found.', code=ErrorCode.APP_NOT_FOUND
            )
        # 仅允许下面这些位于 pyape.app 中的变量。若有修改需要同步更新。
        if not global_name in ('gapp', 'gconf', 'gdb', 'grc', 'gcache', 'logger'):
            raise AppError(
                f'No Global Package Name: {global_name}',
                code=ErrorCode.APP_NOT_FOUND,
            )
        if getattr(mod, global_name, None) is not None:
            raise AppError(
                f'Duplicate definitions are not allowed: {global_name}',
                code=ErrorCode.DUP_DEF,
            )
        return mod

    def set_package_global(
        self,
        global_name: str,
        global_object: Self
        | 'PyapeDB'
        | 'PyapeRedis'
        | GlobalCache
        | GlobalConfig
        | logging.Logger,
    ):
        """设置主包中的全局变量名称。"""
        mod = self.check_package_name(global_name)
        setattr(mod, global_name, global_object)

    def init_db(self) -> 'PyapeDB':
        """初始化 SQLAlchemy 数据库支持。"""
        sql_uri = self.gconf.getcfg('SQLALCHEMY', 'URI')
        if sql_uri is None:
            warnings.warn(f'SQLALCHEMY is not found, ignore init_db.')
            return
        global_name = 'gdb'
        self.check_package_name(global_name)

        # 若传递了 dbinst 则使用其初始化 PyapeDB
        gdb = PyapeDB(app=self, dbinst=self.create_arg.dbinst)
        self.set_package_global(global_name, gdb)
        self.gdb = gdb
        return gdb

    def init_redis(self) -> 'PyapeRedis':
        """初始化 REDIS ，配置文件中包含 REDIS_URI 才进行初始化。"""
        redis_uri = self.gconf.getcfg('REDIS', 'URI')
        if redis_uri is None:
            warnings.warn(f'REDIS is not found, ignore init_redis.')
            return

        global_name = 'grc'
        self.check_package_name(global_name)

        grc = PyapeRedis(app=self)
        self.set_package_global(global_name, grc)
        self.grc = grc
        return grc

    def init_cache(self) -> GlobalCache:
        """初始化全局缓存对象。
        依赖 init_redis，务必在 init_redis 之后调用。
        """
        global_name = 'gcache'
        self.check_package_name(global_name)

        cache_type = None
        kwargs = {}
        if self.grc is None:
            if uwsgiproxy.in_uwsgi:
                cache_type = 'uwsgi'
            else:
                cache_type = 'file'
                kwargs['fpath'] = self.gconf.getdir('cache.toml')
        else:
            cache_type = 'redis'
            kwargs['grc'] = self.grc

        gcache = GlobalCache.from_config(cache_type, **kwargs)
        self.set_package_global(global_name, gcache)
        self.gcache = gcache
        return gcache

    def get_loggers(self) -> list[logging.Logger]:
        """每个框架有自己的 log，因此需要子类来获取并返回。"""
        raise NotImplementedError(f'{self.__class__.__name__}.get_loggers')

    def init_logger(self):
        """设置 logger。可能会依赖其他模块的 logger，因此需要最后调用。"""
        global_name = 'logger'
        self.check_package_name(global_name)

        handler = None
        level = logging.DEBUG
        if self.debug:
            handler = get_logging_handler('stream', 'text', level)
        else:
            name = self.gconf.getcfg('NAME')
            if name is None:
                logger_name = 'app'
            else:
                logger_name = f'app.{name}'
            level = logging.INFO
            handler = get_pyzog_handler(
                logger_name,
                self.gconf.getcfg('LOGGER'),
                self.gconf.getdir('logs'),
                level=level,
            )

        __loggers = self.get_loggers()
        for log in __loggers:
            log.setLevel(level)

        # 加入数据库的 logger
        if self.gdb is not None:
            sqlalchemylogger = logging.getLogger('sqlalchemy')
            sqlalchemylogger.setLevel(logging.WARNING)
            __loggers.append(sqlalchemylogger)

        for log in __loggers:
            log.addHandler(handler)

        self.set_package_global(global_name, __loggers[0])
        self.logger = __loggers[0]
        return self.logger

    def register_a_router(self, router_obj: FrameworkRouter, url_prefix: str):
        raise NotImplementedError(f'{self.__class__.__name__}.register_a_router')

    def register_routers(self):
        """注册路由，必须在 gdb 的创建之后调用。
        """
        appmodules = self.gconf.getcfg('PATH', 'modules')
        for name, url in appmodules.items():
            router_module = importlib.import_module('.' + name, self.PROJECT_PACKAGE_NAME)
            # name 可能为 app.name 这样的复合包，这种情况下，路由实例的名称必须设置为 app_name。
            router_name = name.replace('.', '_')
            router_obj = getattr(router_module, router_name)
            self.register_a_router(router_obj, url)


class PyapeDB(SQLAlchemy):
    """封装 pyape 使用的数据库方法。

    :param app: PyapaFlask 的实例。
    :param dbinst: SQLAlchemy 或者 DBManager 的实例。
    """

    _gconf: GlobalConfig = None
    _app: PyapeApp = None

    # 根据 bind_key 动态生成的 table class，存储在这个 dict 中
    # 位于 pyape.app.models 中的 valueobject 和 regional，
    # 由于在框架内部，无法在项目建立的时候就知道数据库的数量，需要动态创建 table class
    # 动态创建的 class 就保存在这个 dict 中
    __dynamic_table_cls: dict = None

    # 保存根据 regional 进行分类的表定义
    __regional_table_cls: dict = None

    def __init__(self, app: PyapeApp, dbinst: SQLAlchemy | DBManager = None):
        self.__dynamic_table_cls = {}
        self.__regional_table_cls = {}
        self._app = app
        self._gconf = app.gconf

        # 支持从一个已有的 dbinst 对象中共享 dbm 对象。用于项目中有多套 SQLAlchemy 的情况。
        if isinstance(dbinst, SQLAlchemy):
            super().__init__(dbm=dbinst.dbm, is_scoped=True, in_flask=True)
        elif isinstance(dbinst, DBManager):
            super().__init__(dbm=dbinst, is_scoped=True, in_flask=True)
        else:
            sql_uri = self._gconf.getcfg('SQLALCHEMY', 'URI')
            sql_options = self._gconf.getcfg('SQLALCHEMY', 'ENGINE_OPTIONS')
            super().__init__(
                URI=sql_uri, ENGINE_OPTIONS=sql_options, is_scoped=True, in_flask=True
            )

    def get_app(self, reference_app: FrameworkApp = None) -> FrameworkApp:
        if reference_app is not None:
            return reference_app
        return self._app.app

    def __get_dynamic_table_key(self, table_name: str, bind_key: str) -> str:
        """获取一个用于存储动态生成的 table class 的键名。
        键名是采用 bind_key 和 table_name 拼接而成，
        但 bind_key 会有 None 值的情况，将 None 值转换成为空字符串。
        """
        bind_prefix: str = bind_key or ''
        return f'{bind_prefix}_{table_name}'

    def get_dynamic_table(self, table_name: str, bind_key: str = None):
        """获取动态表。"""
        return self.__dynamic_table_cls.get(
            self.__get_dynamic_table_key(table_name, bind_key)
        )

    def set_dynamic_table(
        self, build_table_method: Callable, table_name: str, bind_key: str = None
    ):
        """获取动态表

        :param table: 已经创建好的 table_cls
        :param build_table_method: 创建表的方法，接受两个参数，
            动态创建一个 Table Class，参见 ``pyape.app.models.valueobject.make_value_object_table_cls``。
        """
        key_name: str = self.__get_dynamic_table_key(table_name, bind_key)
        table = self.get_dynamic_table(table_name, bind_key)
        if table is not None:
            raise KeyError(key_name)
        table = build_table_method(table_name, bind_key)
        self.__dynamic_table_cls[key_name] = table
        return table

    def build_regional_tables(
        self, name: str, build_table_method, rconfig: RegionalConfig
    ):
        """根据 regionals 的配置创建多个表。

        :param name: 表的名称前缀。
        :param build_table_method: 创建表的方法，接受两个参数，动态创建一个 Table Class。
        :param rconfig: ``RegionalConfig`` 的实例。
        """
        tables = self.__regional_table_cls.get(name)
        if tables is None:
            tables = {}
            self.__regional_table_cls[name] = tables
        for regional in rconfig.rlist:
            r = regional.get('r')

            # 避免重复建立表
            if tables.get(r) is not None:
                continue

            # 默认使用键名 bind_key_db，若找不到则使用键名 bind_key。
            bind_key = regional.get('bind_key_db')
            Cls = build_table_method(f'{name}{r}', bind_key=bind_key)
            tables[r] = Cls
        # logger.info('build_regional_tables %s', tables)

    def get_regional_table(
        self, name: str, r: int, build_table_method, rconfig: RegionalConfig
    ):
        """根据 regionals 和表名称前缀获取一个动态创建的表。

        :param name: 表的名称前缀。
        :param r: regional。
        :param rconfig: ``RegionalConfig`` 的实例。
        """
        if not r in rconfig.rids:
            raise ValueError('get_regional_table: No regional %s' % r)
        tables = self.__regional_table_cls.get(name)
        Cls = None
        if isinstance(tables, dict):
            Cls = tables.get(r)
        if Cls is None:
            # 可能存在更新了 regional 之后，没有更新 tables 的情况，这里要更新一次。
            # 每个进程都需要更新，但每次调用可能仅发生在其中一个进程。因此必须在每次调用的时候都检测更新。
            self.build_regional_tables(name, build_table_method, self._gconf)
            return self.__regional_table_cls.get(name)
        # logger.info('get_regional_table %s', Cls)
        return Cls

    def result2dict(
        self,
        result: dict | RowMapping | Row,
        keys: Sequence[str],
        replaceobj: dict = None,
        replaceobj_key_only: bool = False,
    ) -> dict:
        """根据提供的 keys、replaceobj、replaceobj_key_only 转换 result 为 dict。

        :param result: 要转换的对象。
        :param keys: 要转换对象的key list。
        :param replaceobj: 可替换的键。
        :param replaceobj_key_only: 仅包含可替换的键。
        :return: 转换成功的 dict。
        """
        result_dict = {}
        for key in keys:
            value = (
                result.get(key) if isinstance(result, dict) else getattr(result, key)
            )
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, Decimal):
                value = int(value)
            newkey = key
            if replaceobj:
                # 仅使用 replaceobj 中提供的键名
                # 这样在找不到键名的时候，newkey 的值为 None
                if replaceobj_key_only:
                    newkey = replaceobj.get(key, None)
                # 找不到对应键名，就使用原始键名
                else:
                    newkey = replaceobj.get(key, key)
            if newkey:
                result_dict[newkey] = value
        return result_dict

    def to_response_data(
        self,
        result: list | dict | Result | Row,
        replaceobj: dict = None,
        replaceobj_key_only: bool = False,
    ):
        """把数据库查询出来的 ResultProxy 转换成标准的 dict 或者 list，
        支持 Result/list[Row]/dict 类型，
        dict 中的值不能包含嵌套的 ResultProxy 对象。

        :param result: 要处理的对象，可以是 list[Row]/dict/Result/Row。
        :param replaceobj: 替换键名。
        :param replaceobj_key_only: 仅使用替换键名，丢掉非替换键名的键。
        """
        if result is None:
            return {}
        if isinstance(result, list):
            return [
                self.to_response_data(item, replaceobj, replaceobj_key_only)
                for item in result
            ]
        elif isinstance(result, dict):
            if replaceobj is None:
                return result
            return self.result2dict(
                result, result.keys(), replaceobj, replaceobj_key_only
            )
        elif isinstance(result, Result):
            if replaceobj is None:
                return [item._asdict() for item in result.all()]
            return [
                self.result2dict(item, item._fields, replaceobj, replaceobj_key_only)
                for item in result.all()
            ]
        elif isinstance(result, Row):
            if replaceobj is None:
                return result._asdict()
            return self.result2dict(
                result, result._fields, replaceobj, replaceobj_key_only
            )
        return result


class PyapeRedis:
    """基于 flask-redis 修改
    增加 根据 Regional 获取 redis client 的封装
    https://github.com/underyx/flask-redis
    """

    _gconf: GlobalConfig = None
    _rconf: RegionalConfig = None

    _client: Redis = None
    """ 保存对应 REDIS_URI 的 redis client 对象。"""

    _client_binds: dict = None
    """ 保存对应 REDIS_BINDS 的 redis client 对象。"""

    _uri: str = None
    """ 配置文件中的 REDIS_URI 的值。"""

    _uri_binds: dict = None
    """ 配置文件中的 REDIS_BINDS 的值。"""

    def __init__(
        self,
        app: PyapeApp = None,
        gconf: GlobalConfig = None,
        config_prefix="REDIS",
        **kwargs,
    ):
        if app is None and gconf is None:
            raise ValueError('Either app or gconf must be present.')
        self.provider_kwargs = kwargs
        self.config_prefix = config_prefix

        self.config_uri = f'{config_prefix}_URI'
        self.config_binds = f'{config_prefix}_BINDS'

        # 保存 REDIS_URI 中设定的那个连接
        self._client: Redis = None
        # 以 bind_key 保存 Client，其中 self._redis_client 将 None 作为 bind_key 保存
        self._client_binds = None

        if app is not None:
            self._gconf = app._gconf
            self._rconf = app._gconf.regional
            self.init_app(app)
        else:
            self._gconf = gconf
            self._rconf = gconf.regional
            self.init_redis()

    def init_app(self, app: PyapeApp, **kwargs):
        """初始化 redis 连接，并将  REDIS 写入 Flask 的 extensions 对象。"""
        self.init_redis(**kwargs)

        if not hasattr(app.app, 'extensions'):
            app.app.extensions = {}
        app.app.extensions[self.config_prefix.lower()] = self

    def init_redis(self, **kwargs):
        """仅初始化 redis 连接。"""
        self.provider_kwargs.update(kwargs)
        self._uri = self._gconf.getcfg(
            self.config_uri, default_value='redis://localhost:6379/0'
        )
        self._client = Redis.from_url(self._uri, **self.provider_kwargs)
        self._update_binds()

    def _update_binds(self):
        self._uri_binds = self._gconf.getcfg(self.config_binds)
        self._client_binds = {None: self._client}
        if isinstance(self._uri_binds, dict):
            for bind_key, bind_uri in self._uri_binds.items():
                self._client_binds[bind_key] = Redis.from_url(
                    bind_uri, **self.provider_kwargs
                )

    def get_uri(self, bind_key: str = None, miss_default: bool = False) -> str:
        """获取一个 redis uri 地址。

        :param bind_key: 绑定的值，可以为 None
        :param miss_default: 若找不到 bind_key 中的对应 uri，就使用默认的 self._uri。
        """
        return self._uri_binds.get(bind_key, self._uri if miss_default else None)

    def get_client(self, bind_key: str = None, miss_default: bool = False) -> Redis:
        """获取一个 redis client。

        :param bind_key: 绑定的值，可以为 None
        :param miss_default: 若找不到 bind_key 中的对应 client，就使用默认的 self._client。
        """
        return self._client_binds.get(bind_key, self._client if miss_default else None)

    def get_clients(self) -> dict[str, Redis]:
        return self._client_binds

    def get_regional_client(self, r: int, force: bool = True) -> Redis:
        """根据 r 获取到一个 py_redis_client

        :param r: regional
        :param force: 没有 redis 配置会抛出 ValueError 异常。若设置为 False 则返回 None（无异常）
        """
        if not r in self._rconf.rids:
            if force:
                raise ValueError('get_redis_client: no regional %s' % r)
            return None
        robj = self._rconf.rdict.get(r)
        # bind_key_redis 如果没有定义，或者为 None，就会得到默认的 REDIS_URI
        return self.get_client(robj.get('bind_key_redis'))

    def get_regional_clients(self):
        """获取到一个以 regional 为键名的 py_redis_client dict"""
        clients = {}
        rc_clients = self.get_clients()
        for r, robj in self._rconf.rdict.items():
            # bind_key_redis 如果没有定义，或者为 None，就会得到默认的 REDIS_URI
            bind_key_redis = robj.get('bind_key_redis')
            clients[r] = rc_clients[bind_key_redis]
        return clients
