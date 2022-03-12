"""
pyape.app
----------------------

处理 app 初始化，与 flask 强相关
"""

import importlib
from pathlib import Path
import sys
import logging
from functools import wraps

import flask

from flask_compress import Compress

from pyape import uwsgiproxy
from pyape import errors
from pyape.config import GlobalConfig
from pyape.cache import GlobalCache
from pyape.logging import get_logging_handler, get_pyzog_handler
from pyape.flask_extend import PyapeFlask, PyapeResponse, FlaskConfig, PyapeDB, PyapeRedis


# 全局配置对象
gconfig: GlobalConfig = None

# 全局的数据库引用，保存的是 PyapeDB 的实例
gdb: PyapeDB = None

# grc 就是 Global Redis Client 的缩写，pyape.flask_redis.FlaskRedis 的实例
grc: PyapeRedis = None

# 全局缓存实例，pyape.cache.GlobalCache 的实例
gcache: GlobalCache = None

# 就是 flas.app.logger 放在这里不必引用 current_app，参考：
# https://flask.palletsprojects.com/en/1.1.x/logging/
logger: logging.Logger = logging.getLogger(__name__)


def init_db(pyape_app: PyapeFlask):
    """ 初始化 SQLAlchemy
    """
    sql_uri = pyape_app._gconf.getcfg('SQLALCHEMY', 'URI')
    if sql_uri is None:
        return
    global gdb
    if gdb is not None:
        raise ValueError('gdb 不能重复定义！')
    gdb = PyapeDB(app=pyape_app)
    pyape_app._gdb = gdb


def init_redis(pyape_app: PyapeFlask):
    """ 初始化 REDIS ，配置文件中包含 REDIS_URI 才进行初始化
    """
    redis_uri = pyape_app._gconf.getcfg('REDIS', 'URI')
    if redis_uri is None:
        return
    global grc
    if grc is not None:
        raise ValueError('redis client 不能重复定义！')
    grc = PyapeRedis(app=pyape_app)


def init_logger(pyape_app: PyapeFlask):
    """ 设置 Flask app 和 sqlalchemy 的logger
    """
    flasklogger = pyape_app.logger
    sqlalchemylogger = logging.getLogger('sqlalchemy')
    # 删除 Flask 的默认 Handler
    del flasklogger.handlers[:]
    handler = None
    level = logging.DEBUG

    if pyape_app.config.get('DEBUG'):
        handler = get_logging_handler('stream', 'text', level)
    else:
        name = pyape_app._gconf.getcfg('NAME')
        if name is None:
            logger_name = 'app'
        else:
            logger_name = f'app.{name}'
        level = logging.INFO
        handler = get_pyzog_handler(logger_name, pyape_app._gconf.getcfg('LOGGER'), pyape_app._gconf.getdir('logs'), level=level)

    flasklogger.setLevel(level)
    sqlalchemylogger.setLevel(logging.WARNING)
    for log in (flasklogger, sqlalchemylogger):
        log.addHandler(handler)


def init_cache(pyape_app: PyapeFlask):
    """ 初始化全局缓存对象
    """
    global gcache
    if gcache is not None:
        raise ValueError('global cache 不能重复定义！')
    ctype = None
    flask_redis_client = None
    if grc is None:
        if uwsgiproxy.in_uwsgi:
            ctype = 'uwsgi'
        else:
            ctype = 'dict'
    else:
        flask_redis_client = grc.get_client(bind_key='cache')
        if flask_redis_client is None:
            flask_redis_client = grc.get_client()
    gcache = GlobalCache.from_config(ctype, flask_redis_client=flask_redis_client)


def register_blueprint(pyape_app, rest_package, rest_package_names):
    """ 注册 Blueprint，必须在 db 的创建之后调用
    :param app: flask app 实例
    :param rest_package: 父包名
    :param rest_package_names: {name:url, name2:url2}
    :return:
    """
    if rest_package is None:
        return
    for name, url in rest_package_names.items():
        bp_module = importlib.import_module('.' + name, rest_package)
        # name 可能为 app.name 这样的复合包，这种情况下，Blueprint 实例的名称为 app_name
        bp_name = name.replace('.', '_')
        pyape_app.register_blueprint(getattr(bp_module, bp_name), url_prefix=url)


def _build_kwargs_for_app(gconf: GlobalConfig):
    """ 将本地所有路径转换为绝对路径，以保证其在任何环境下可用
    """
    kwargs = {
            'static_url_path': gconf.getcfg('PATH', 'STATIC_URL_PATH', default_value=''),
            'static_folder': gconf.getcfg('PATH', 'STATIC_FOLDER', default_value='static'),
            'template_folder': gconf.getcfg('PATH', 'TEMPLATE_FOLDER', default_value='templates')
        }

    instance_path = gconf.getcfg('PATH', 'INSTANCE_PATH')
    if instance_path:
        kwargs['instance_path'] = gconf.getdir(instance_path).resolve().as_posix()
    else:
        kwargs['instance_path'] = gconf.getdir().resolve().as_posix()

    kwargs['template_folder'] = gconf.getdir(kwargs['template_folder']).resolve().as_posix()
    kwargs['static_folder'] = gconf.getdir(kwargs['static_folder']).resolve().as_posix()
    return kwargs


def create_app(gconf: GlobalConfig, FlaskClass=PyapeFlask, ResponseClass=PyapeResponse, ConfigClass=FlaskConfig):
    """
    根据不同的配置创建 app
    :param config_name:
    :return:
    """
    kwargs = _build_kwargs_for_app(gconf)

    pyape_app = FlaskClass(__name__, gconf=gconf, **kwargs)
    pyape_app.response_class = ResponseClass
    pyape_app.config.from_object(ConfigClass(gconf.getcfg('FLASK')))
    if pyape_app.config.get('COMPRESS_ON'):
        # 压缩 gzip
        compress = Compress()
        compress.init_app(pyape_app)
    # 处理全局错误
    errors.init_app(pyape_app)
    return pyape_app


def _init_common(gconf: GlobalConfig=None, cls_config=None) -> PyapeFlask:
    if gconf is None:
        gconf = GlobalConfig(Path.cwd())
    sys.modules[__name__].__dict__['gconfig'] = gconf
    flask.cli.load_dotenv()

    pyape_app = create_app(gconf ,**cls_config) if isinstance(cls_config, dict) else create_app(gconf)

    init_db(pyape_app)
    init_redis(pyape_app)
    # logger 可能会使用 redis，因此顺序在 redis 初始化之后
    init_logger(pyape_app)
    # cache 可能会使用 redis，因此顺序在 redis 初始化之后
    init_cache(pyape_app)
    
    return pyape_app


def init(gconf: GlobalConfig=None, init_app_method=None, cls_config=None) -> PyapeFlask:
    """ 初始化 APP

    :param gconf: pyape.config.GlobalConfig 的实例
    :param init_app: 外部初始化方法
    :param cls_config: 一个包含自定义 Class 的 dict
        形如: ``{'FlaskClass': PyapeFlask, 'ResponseClass': PyapeResponse, 'ConfigClass': FlaskConfig}``
        不需要同时包含 3 个 Class
    """
    pyape_app = _init_common(gconf, cls_config)

    # 这个方法必须在注册蓝图前调用
    if init_app_method is not None:
        init_app_method(pyape_app)

    # blueprint 要 import gdb，因此要在 gdb 之后注册
    appmodules = gconf.getcfg('PATH', 'modules')
    register_blueprint(pyape_app, 'app', appmodules)
    return pyape_app


def init_decorator(gconf: GlobalConfig=None, cls_config=None):
    """ 初始化 APP 的装饰器版本

    :param gconf: pyape.config.GlobalConfig 的实例
    :param init_app: 外部初始化方法
    :param cls_config: 一个包含自定义 Class 的 dict
        形如: ``{'FlaskClass': PyapeFlask, 'ResponseClass': PyapeResponse, 'ConfigClass': FlaskConfig}``
        不需要同时包含 3 个 Class
    """
    pyape_app = _init_common(gconf, cls_config)

    def decorator(f):
        @wraps(f)
        def decorated_fun(*args, **kwargs):
            kwargs['pyape_app'] = pyape_app
            # 在外部调用中需要做：
            # 1. 导入外部的 models
            # 2. 创建数据库
            # 这里不传递 *args 这个参数，因为在 uwsgi 中这个参数有不少来自于服务器的值，
            # 这会导致 f 调用失败，f 仅接受 pyape_app 这个参数
            decorated_return = f(**kwargs)

            # blueprint 要 import gdb，因此要在 gdb 之后注册
            appmodules = gconf.getcfg('PATH', 'modules')
            register_blueprint(pyape_app, 'app', appmodules)
            return decorated_return

        return decorated_fun

    return decorator
