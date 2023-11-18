"""
pyape.error
-------------------

定义所有 pyape 的错误。
"""

from enum import IntEnum, auto


class ErrorCode(IntEnum):
    DEFAULT = auto()
    """ 默认错误。"""

    REQUIRED_CONF = auto()
    """ 缺少必须的配置。"""

    ENV_NAME = auto()
    """ 没有提供正确的 env。"""

    DEPLOY_DIR = auto()
    """ 配置中的 deploy_dir 路径错误。"""

    REPLACE_KEY_ERROR = auto()
    """ 配置替换时发生 KeyError。"""

    WEBHOOK = auto()
    """ webhook 配置错误。"""

    APP_NOT_FOUND = auto()
    """ 在 PyapeApp 实例中没有找到对应的框架 app 设置。"""

    DUP_DEF = auto()
    """ 核心库（gdb, gconf）重复定义。"""


class PyapeError(Exception):
    code: ErrorCode = ErrorCode.DEFAULT
    """ 错误代码。"""

    message: str = None
    """ 错误消息。"""

    def __init__(self, message: str, code: ErrorCode=ErrorCode.DEFAULT, *args: object) -> None:
        super().__init__(*args)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message if self.message else f'{self.__class__.__name__} {self.code.name}'


class AppError(PyapeError):
    """ App 核心错误消息。"""
    pass


class ConfigError(PyapeError):
    """ 配置文件错误消息。"""
    pass


