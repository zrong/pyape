"""
pyape.flask
----------------------

对 Flask 框架进行扩展。
"""
import logging

import flask
import flask.cli
from flask_compress import Compress
from flask import Flask, Response, request, Blueprint, jsonify, flash
from flask.sessions import SecureCookieSessionInterface
from werkzeug.datastructures import Headers

from .config import GlobalConfig, Dicto
from .error import ErrorCode, ConfigError
from .application import CreateArgument, PyapeApp, PyapeDB
from .db import DBManager, SQLAlchemy
from .util.date import jinja_filter_strftimestamp


def flash_dict(d, category: str = 'message'):
    """将 dict 中的每一项转换为一行进行 flash 输出"""
    s = []
    for k, v in d.items():
        s.append(f'{k}: {", ".join(v)}')
    flash(' '.join(s), category)


def forbidden(e):
    response = jsonify({'error': True, 'code': 403, 'message': '403 forbidden'})
    response.status_code = 403
    return response


def page_not_found(e):
    response = jsonify({'error': True, 'code': 404, 'message': '404 not found'})
    response.status_code = 404
    return response


def method_not_allowed(e):
    response = jsonify({'error': True, 'code': 405, 'message': '405 method not allowed'})
    response.status_code = 405
    return response


def internal_server_error(e):
    response = jsonify({'error': True, 'code': 500, 'message': '500 internal server error'})
    response.status_code = 500
    return response


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


class PyapeDBFlask(PyapeDB):
    def __init__(self, app: PyapeApp, dbinst: SQLAlchemy | DBManager = None):
        super().__init__(app, dbinst)

        flask_app: Flask = app.app

        @flask_app.teardown_appcontext
        def shutdown_session(response_or_exc):
            # flask_app.logger.info(f'PyapeDB.Session.remove: {self.Session}')
            # https://docs.sqlalchemy.org/en/14/orm/contextual.html
            self.Session.remove()
            return response_or_exc


_default_create_arg = CreateArgument(
    FrameworkAppClass=PyapeFlask,
    ResponseClass=PyapeResponse,
    ConfigClass=FlaskConfig,
    error_handler=False,
)
""" create_arg 的值

    FrameworkAppClass: Flask 的子类。
    ResponseClass: Flask Response 的子类。
    ConfigClass:  对 flask.config 进行包装。
    error_handler: 是否启用 ``Flask.register_error_handler``
    接管 HTTP STATUS_CODE 处理。若值为 True，则使用 ``pyape.errors`` 来接管。
"""


class PyapeAppFlask(PyapeApp):
    """Flask 的专用 App，管理 Flask 对象的初始化工作。"""

    def __init__(
        self,
        gconf: GlobalConfig,
        create_arg: CreateArgument = None,
        package_name: str = 'pyape.app',
    ) -> None:
        super().__init__(gconf, create_arg, package_name)
        if self.create_arg is None:
            self.create_arg = CreateArgument(_default_create_arg)
        else:
            merge_args = CreateArgument(_default_create_arg)
            merge_args.update(self.create_arg)
            self.create_arg = merge_args

        flask.cli.load_dotenv()

        self.framework_app = self.create_app()
        # 增加自定义 jinja filter
        self.app.add_template_filter(jinja_filter_strftimestamp, 'strftimestamp')
        self.init_db()
        self.init_redis()

        # cache 可能会使用 redis，因此顺序在 redis 初始化之后
        self.init_cache()

        # logger 可能会使用 redis，因此顺序在 redis 初始化之后
        self.init_logger()

        if self.create_arg and self.create_arg.init_app_method:
            self.create_arg.init_app_method(self)

        # blueprint 要 import gdb，因此要在 gdb 之后注册
        self.register_routers()

    @property
    def debug(self) -> bool:
        return self.app.debug

    @property
    def app(self) -> PyapeFlask:
        if flask.current_app:
            # https://werkzeug.palletsprojects.com/en/2.0.x/local/#werkzeug.local.LocalProxy._get_current_object
            # No application found. Either work inside a view function or push
            # an application context. See
            # http://flask-sqlalchemy.pocoo.org/contexts/.
            return flask.current_app._get_current_object()
        return super().app

    def _get_flask_config(self) -> dict:
        """ 更新 Flask 的配置文件。"""
        flask_config_dict = self.gconf.getcfg('FLASK', default_value={})
        secret_key_in_flask = flask_config_dict.get('SECRET_KEY')
        if secret_key_in_flask is None:
            flask_config_dict['SECRET_KEY'] = self.gconf.getcfg('SECRET_KEY')
        if not flask_config_dict.get('SECRETE_KEY'):
            raise ConfigError('SECRET_KEY or FLASK.SECRET_KEY is not in config.toml!', ErrorCode.REQUIRED_CONF)
        return flask_config_dict

    def create_app(self) -> PyapeFlask:
        FlaskClass = self.create_arg.FrameworkAppClass
        ResponseClass = self.create_arg['ResponseClass']
        ConfigClass = self.create_arg['ConfigClass']
        error_handler = self.create_arg['error_handler']

        flask_init_kwargs = self._build_kwargs_for_app()

        flask_app = FlaskClass(__name__, gconf=self.gconf, **flask_init_kwargs)
        flask_app.response_class = ResponseClass
        flask_config_dict = self.gconf.getcfg('FLASK')
        flask_app.config.from_object(ConfigClass(self._get_flask_config()))
        if flask_app.config.get('COMPRESS_ON'):
            # 压缩 gzip
            compress = Compress()
            compress.init_app(flask_app)
        # 处理全局错误
        if error_handler:
            self.register_error_handler(flask_app)
        return flask_app

    def register_error_handler(self, flask_app: PyapeFlask):
        flask_app.register_error_handler(403, forbidden)
        flask_app.register_error_handler(404, page_not_found)
        flask_app.register_error_handler(405, method_not_allowed)
        flask_app.register_error_handler(500, internal_server_error)
        # flask_app.error_handler_spec[None][403] = forbidden
        # flask_app.error_handler_spec[None][404] = page_not_found
        # flask_app.error_handler_spec[None][405] = method_not_allowed
        # flask_app.error_handler_spec[None][500] = internal_server_error

    def register_a_router(self, router_obj: Blueprint, url_prefix: str):
        self.app.register_blueprint(router_obj, url_prefix=url_prefix)

    def _build_kwargs_for_app(self):
        """将本地所有路径转换为绝对路径，以保证其在任何环境下可用。"""
        kwargs = {
            'static_url_path': self.gconf.getcfg(
                'PATH', 'STATIC_URL_PATH', default_value=''
            ),
            'static_folder': self.gconf.getcfg(
                'PATH', 'STATIC_FOLDER', default_value='static'
            ),
            'template_folder': self.gconf.getcfg(
                'PATH', 'TEMPLATE_FOLDER', default_value='templates'
            ),
        }

        instance_path = self.gconf.getcfg('PATH', 'INSTANCE_PATH')
        if instance_path:
            kwargs['instance_path'] = (
                self.gconf.getdir(instance_path).resolve().as_posix()
            )
        else:
            kwargs['instance_path'] = self.gconf.getdir().resolve().as_posix()

        kwargs['template_folder'] = (
            self.gconf.getdir(kwargs['template_folder']).resolve().as_posix()
        )
        kwargs['static_folder'] = (
            self.gconf.getdir(kwargs['static_folder']).resolve().as_posix()
        )
        return kwargs

    def get_loggers(self) -> list[logging.Logger]:
        flasklogger = self.app.logger
        # 删除 Flask 的默认 Handler
        del flasklogger.handlers[:]
        return [flasklogger]
