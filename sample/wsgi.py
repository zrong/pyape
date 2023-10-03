from pathlib import Path
from functools import partial

try:
    import pyape
except ImportError:
    # 若处于 pyape 开发环境下，需要将其搜索路径加入 path
    import sys
    sys.path.insert(0, Path(__file__).parent.parent.resolve().as_posix())

import pyape.app
import pyape.config
from pyape.flask import PyapeFlask, PyapeResponse

# 工作文件夹
work_dir = Path(__file__).parent.resolve()
# 读取主配置文件 config.toml
gconfig = pyape.config.GlobalConfig(work_dir)


class CustomResponse(PyapeResponse):
    @property
    def cors_config(self):
        return PyapeResponse.CORS_DEFAULT


def setup_app(pyape_app: PyapeFlask, **kwargs):
    """ 初始化 app 项目，这个方法被嵌入 flask shell 上下文中执行，可以使用 kwargs 传递参数
    """
    # 导入所有的 Model 定义
    import app.model
    pyape_app._gdb.create_all()
    return pyape_app
    

def create_app(pyape_app: PyapeFlask):
    """ 被 pyape.app.init 调用，用于处理 app 初始化
    """
    # 加入上下文处理器
    pyape_app.shell_context_processor(lambda: {
        'gdb': pyape_app._gdb,
        # 这里可以传递更多促使给 setup_app
        'setup': partial(setup_app, pyape_app),
    })
    pyape.app.logger.info(pyape_app.config)


# gconfig 可以设置为 None，此时会使用 Path.cwd() 下的 config.toml 作为配置文件。
sample_app: PyapeFlask = pyape.app.init(gconfig, create_app, create_args={'ResponseClass': CustomResponse})
