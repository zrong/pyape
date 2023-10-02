"""
pyape.flask_extend
----------------------

对 Flask 框架进行扩展。
"""
from typing import Callable, Any
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import flask
from flask import Flask, Response, request
from flask.sessions import SecureCookieSessionInterface
from werkzeug.datastructures import Headers
from sqlalchemy.inspection import inspect
from sqlalchemy.engine import Row, RowMapping, Result
from redis.client import Redis

from pyape.config import GlobalConfig, Dicto, RegionalConfig
from pyape.db import SQLAlchemy, DBManager


class PyapeSecureCookieSessionInterface(SecureCookieSessionInterface):
    """修改 Flask 框架的默认 salt，并提供 Flask Session 的加解密功能。"""

    def __init__(self) -> None:
        self.salt = 'pyape-cookie-session'
        super().__init__()

    @classmethod
    def decode_flask_cookie(cls, secret_key: str, cookie: str):
        """解码 flask cookie-session 字符串。"""
        pscsi = cls()
        # get_signing_serializer 方法需要一个 Flask 实例，其中只需要包含 secret_key 即可。
        fake_app: Dicto = Dicto(secret_key=secret_key)
        serializer = pscsi.get_signing_serializer(fake_app)
        return serializer.loads(cookie)

    @classmethod
    def encode_flask_cookie(cls, secret_key: str, cookie: dict):
        """将 dict 编码成 flask cookie-session 字符串。"""
        pscsi = cls()
        # get_signing_serializer 方法需要一个 Flask 实例，其中只需要包含 secret_key 即可。
        fake_app: Dicto = Dicto(secret_key=secret_key)
        serializer = pscsi.get_signing_serializer(fake_app)
        return serializer.dumps(cookie)


class FlaskConfig(object):
    """flask.config.from_object 不支持 dict，因此建立这个 class。"""

    # ALLOWED_EXTENSIONS = set([])
    BOOTSTRAP_SERVE_LOCAL = True
    LOGGER_HANDLER_POLICY = 'never'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    def __init__(self, cfgdef=None):
        if cfgdef:
            self.from_object(cfgdef)
        self.check_must_keys()

    def check_must_keys(self):
        for key in ('SECRET_KEY',):
            if getattr(self, key, None) is None:
                raise ValueError('No ' + key)

    def from_object(self, obj):
        for key, value in obj.items():
            setattr(self, key, value)


class PyapeResponse(Response):
    """自定义的响应，为所有的响应头加入跨域信息。"""

    # 默认的跨域数据
    # https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Access_control_CORS
    CORS_DEFAULT = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'HEAD, OPTIONS, GET, POST, PUT, DELETE',
        'Access-Control-Allow-Headers': 'Content-Type',
    }

    def __init__(
        self,
        response=None,
        status=None,
        headers=None,
        mimetype=None,
        content_type=None,
        direct_passthrough=False,
    ):
        if isinstance(self.cors_config, dict):
            if headers:
                for k, v in self.cors_config.items():
                    headers.add(k, v)
            else:
                headers = Headers(self.cors_config.items())
        super().__init__(
            response=response,
            status=status,
            headers=headers,
            mimetype=mimetype,
            content_type=content_type,
            direct_passthrough=direct_passthrough,
        )

    @property
    def cors_config(self):
        """子类覆盖该方法，实现跨域

        例如：

        >>> @property
        >>> def cros_config(self):
        >>>    return PyapeResponse.CORS_DEFAULT
        """
        return None


class PyapeFlask(Flask):
    _gconf: GlobalConfig = None
    _gdb = None

    def __init__(self, *args, gconf: GlobalConfig, **kwargs):
        super().__init__(*args, **kwargs)
        self._gconf = gconf
        self.session_interface = PyapeSecureCookieSessionInterface()

    def log_exception(self, exc_info):
        self.logger.error(
            '%s',
            dict(
                method=request.method,
                path=request.path,
                ip=request.remote_addr,
                agent_platform=request.user_agent.platform,
                agent_browser=request.user_agent.browser,
                agent_browser_version=request.user_agent.version,
                agent=request.user_agent.string,
            ),
            exc_info=exc_info,
        )


class PyapeDB(SQLAlchemy):
    """封装 pyape 使用的数据库方法。

    :param app: PyapaFlask 的实例。
    :param dbinst: SQLAlchemy 或者 DBManager 的实例。
    """

    _gconf: GlobalConfig = None
    _app: PyapeFlask = None

    # 根据 bind_key 动态生成的 table class，存储在这个 dict 中
    # 位于 pyape.app.models 中的 valueobject 和 regional，
    # 由于在框架内部，无法在项目建立的时候就知道数据库的数量，需要动态创建 table class
    # 动态创建的 class 就保存在这个 dict 中
    __dynamic_table_cls: dict = None

    # 保存根据 regional 进行分类的表定义
    __regional_table_cls: dict = None

    def __init__(self, app: PyapeFlask, dbinst: SQLAlchemy | DBManager = None):
        self.__dynamic_table_cls = {}
        self.__regional_table_cls = {}
        self._app = app
        self._gconf = app._gconf

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
        self._app.logger.info(f'self.Session {self.Session}')

        @app.teardown_appcontext
        def shutdown_session(response_or_exc):
            # self._app.logger.info(f'PyapeDB.Session.remove: {self.Session}')
            # https://docs.sqlalchemy.org/en/14/orm/contextual.html
            self.Session.remove()
            return response_or_exc

    def get_app(self, reference_app: PyapeFlask = None) -> PyapeFlask:
        if reference_app is not None:
            return reference_app
        if flask.current_app:
            # https://werkzeug.palletsprojects.com/en/2.0.x/local/#werkzeug.local.LocalProxy._get_current_object
            return flask.current_app._get_current_object()
        if self._app:
            return self._app
        raise RuntimeError(
            'No application found. Either work inside a view function or push'
            ' an application context. See'
            ' http://flask-sqlalchemy.pocoo.org/contexts/.'
        )

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
        app: PyapeFlask = None,
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

    def init_app(self, app: PyapeFlask, **kwargs):
        """初始化 redis 连接，并将  REDIS 写入 Flask 的 extensions 对象。"""
        self.init_redis(**kwargs)

        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions[self.config_prefix.lower()] = self

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


def flash_dict(d, category: str = 'message'):
    """将 dict 中的每一项转换为一行进行 flash 输出"""
    s = []
    for k, v in d.items():
        s.append(f'{k}: {", ".join(v)}')
    flask.flash(' '.join(s), category)


def jinja_filter_strftimestamp(ts, fmt: str = None):
    """将 timestamp 转换成为字符串。"""
    # fmt = '%Y-%m-%d'
    dt = datetime.fromtimestamp(ts)
    if fmt is None:
        return dt.isoformat()
    return dt.strftime(fmt)
