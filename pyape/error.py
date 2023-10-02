"""
pyape.error
-------------------

定义所有 pyape 的错误。
"""

from enum import IntEnum, auto


class ErrorCode(IntEnum):
    DEFAULT = auto()
    """ 默认错误。"""

    ENV_NAME = auto()
    """ 没有提供正确的 env。"""

    DEPLOY_DIR = auto()
    """ 配置中的 deploy_dir 路径错误。"""

    REPLACE_KEY_ERROR = auto()
    """ 配置替换时发生 KeyError。"""


class ConfigError(Exception):
    code: ErrorCode = ErrorCode.DEFAULT
    """ 配置文件中使用的错误代码。"""

    message: str = None
    """ 配置文件出错消息。"""

    def __init__(self, message: str, code: ErrorCode=ErrorCode.DEFAULT, *args: object) -> None:
        super().__init__(*args)
        self.code = code
        self.message = message