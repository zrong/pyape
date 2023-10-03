from pathlib import Path
from functools import partial

import pyape.app
import pyape.config
from pyape.flask.extend import PyapeFlask, PyapeResponse, PyapeAppFlask
from pyape.application import CreateArgument

# 工作文件夹
work_dir = Path(__file__).parent.resolve()
# 读取主配置文件 config.toml
gconfig = pyape.config.GlobalConfig(work_dir)


class CustomResponse(PyapeResponse):
    @property
    def cors_config(self):
        return PyapeResponse.CORS_DEFAULT


def setup_app(gapp: PyapeAppFlask, **kwargs):
    """初始化 app 项目，这个方法被嵌入 flask shell 上下文中执行，可以使用 kwargs 传递参数"""
    # 如果需要，创建默认的 regional，此处应该根据实际的数据库的数量，指定 bind_key
    # 例如 SQLALCHEMY_URI 的值若为一个 dict，则可以采用循环的方式创建不同数据库中的 regional table
    # 此处的 bind_key 的值为范例值，实际使用的时候必须要修改
    # from pyape.app.models.regional import init_regional, make_regional_table_cls
    # gapp.gdb.set_dynamic_table(make_regional_table_cls, table_name='r', bind_key='main')
    # gapp.gdb.create_all()

    # 这里其实不需要在 app 上下文中执行
    # with pyape_app_flask.app.app_context():
    #     # 初始化 models
    #     init_regional()

    # 可以直接执行的
    # init_regional()
    return gapp


def create_app(gapp: PyapeAppFlask):
    """被 pyape.app.init 调用，用于处理 app 初始化"""
    # 加入上下文处理器
    gapp.app.shell_context_processor(
        lambda: {
            'gdb': pyape_app._gdb,
            # 这里可以传递更多促使给 setup_app
            'setup': partial(setup_app, gapp),
        }
    )
    gapp.logger.info(gapp.app.config)


gapp = PyapeAppFlask(
    gconfig,
    CreateArgument(ResponseClass=CustomResponse, init_app_method=setup_app),
    pyape.app.__name__,
)

pyape_app: PyapeFlask = gapp.app
