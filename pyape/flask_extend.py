from werkzeug.datastructures import Headers
from flask import (Flask, Response, request)

from pyape.config import GlobalConfig


class FlaskConfig(object):
    """ flask.config.from_object 不支持 dict，因此建立这个 class
    """
    # ALLOWED_EXTENSIONS = set([])
    BOOTSTRAP_SERVE_LOCAL = True
    LOGGER_HANDLER_POLICY = 'never'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    def __init__(self, cfgdef=None):
        if cfgdef:
            self.from_object(cfgdef)
        self.check_must_keys()

    def check_must_keys(self):
        for key in ('SECRET_KEY', 'SQLALCHEMY_URI'):
            if getattr(self, key, None) is None:
                raise ValueError('No ' + key)

    def from_object(self, obj):
        for key, value in obj.items():
            setattr(self, key, value)


class PyapeResponse(Response):
    """ 自定义的响应，为所有的响应头加入跨域信息 """

    # 默认的跨域数据
    # https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Access_control_CORS
    CORS_DEFAULT = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'HEAD, OPTIONS, GET, POST, PUT, DELETE',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
        
    def __init__(self,
        response=None,
        status=None,
        headers=None,
        mimetype=None,
        content_type=None,
        direct_passthrough=False):
        if isinstance(self.cors_config, dict):
            if headers:
                for k, v in self.cors_config.items():
                    headers.add(k, v)
            else:
                headers = Headers(self.cors_config.items())
        super().__init__(response=response,
            status=status,
            headers=headers,
            mimetype=mimetype,
            content_type=content_type,
            direct_passthrough=direct_passthrough)
    
    @property
    def cors_config(self):
        """ 子类覆盖该方法，实现跨域
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
        self._gconf = gconf
        super().__init__(*args, **kwargs)

    def log_exception(self, exc_info):
        """...description omitted..."""
        self.logger.error('%s', dict(
                method=request.method,
                path=request.path,
                ip=request.remote_addr,
                agent_platform=request.user_agent.platform,
                agent_browser=request.user_agent.browser,
                agent_browser_version=request.user_agent.version,
                agent=request.user_agent.string,
            ), exc_info=exc_info
        )